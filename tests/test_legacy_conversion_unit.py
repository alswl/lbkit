"""Unit tests for legacy conversion and guarded authority publication."""

import fcntl
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from herdr_fixtures import target as herdr_target

from logbook_cli import legacy_migration, observation, unified
from logbook_cli.document import LbError
from logbook_cli.services import execution as execution_service
from logbook_cli.services import readiness, transport
from logbook_cli.services.common import load
from logbook_cli.storage import replace_bytes_at, write_bytes

DOC_ID = "1" * 32
THINKING_ID = "2" * 32
LOG = "docs/delivery.md"
THINKING = "thinking/delivery.md"
TARGET = "lb/migrated.json"
ARCHIVE = "lb/migrated.migration-backup"
SIDE = "lb/delivery.md.json"


class LegacyConversionTest(TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.dump(
            LOG,
            "# Example\n\n## Stage 01 Build\n\n- [/] Build sample\n    <!-- lb-task task-build -->\n",
        )
        self.dump(THINKING, "# Example Thinking\n")
        self.binding = herdr_target()["binding"]
        self.binding.pop("server")
        self.binding |= {
            "observed_at": "2025-01-01T00:00:00Z",
            "basis": "saved runtime inspection",
        }
        self.dispatch = {
            "id": "dispatch-1",
            "log": LOG,
            "log_id": DOC_ID,
            "task_id": "task-build",
            "owner": "agent-example",
            "scope": "example scope",
            "exclusions": "none",
            "inputs": "example input",
            "completion": "example output",
            "escalation": "ask",
            "status": "sent",
            "history": [],
            "attempts": [],
        }
        self.metadata = {
            LOG: {
                "document": self.identity(DOC_ID),
                "task": {"task-build": {"id": "task-build"}},
            },
            THINKING: {
                "document": self.identity(THINKING_ID),
                "dispatch": {"dispatch-1": self.dispatch},
                "agent": {
                    "dispatch-1": self.binding
                    | {
                        "id": "dispatch-1",
                        "log": LOG,
                        "log_id": DOC_ID,
                        "task_id": "task-build",
                    }
                },
            },
        }
        self.dump(SIDE, {"format": "lb-document-state", "documents": self.metadata})
        self.op = {
            "id": "send-1",
            "request": {
                "dispatch_id": "dispatch-1",
                "recipient": "agent-example",
                "session_id": self.binding["session_id"],
                "message_digest": "a" * 64,
                "binding_digest": transport.legacy_digest(
                    self.binding, transport.DISPATCH_BINDING_FIELDS
                ),
                "package_digest": transport.legacy_digest(
                    self.dispatch, transport.DISPATCH_PACKAGE_FIELDS
                ),
            },
            "outcome": "submitted",
            "receipt": {"accepted": True},
            "provenance": "adapter",
        }
        self.old = {
            "name": "old",
            "log": LOG,
            "thinking": THINKING,
            "captain": "captain-example",
            "advancement": "example",
            "facts": [],
            "operations": [self.op],
        }
        self.dump("lb/old.json", self.old)

    @staticmethod
    def identity(value):
        return {"identity": {"id": "identity", "uuid": value}}

    def dump(self, path, data):
        file = self.root / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(data if isinstance(data, str) else json.dumps(data))
        return file

    def run_migration(self, *, token=None, rollback=False):
        return legacy_migration.run(
            str(self.root),
            LOG,
            "migrated",
            [],
            dry_run=token is None,
            is_rollback=rollback,
            token=token,
        )

    def apply(self):
        dry = self.run_migration()
        self.assertEqual(dry.code, 0, dry.value)
        self.assertEqual(dry.value["send_task_mapping"], {"send-1": "task-build"})
        return self.run_migration(token=dry.value["plan_token"])

    def unified(self):
        return unified.read(self.root / TARGET, self.root)

    def test_migrates_bound_dispatch_cancelled_before_send_as_history(self):
        self.dispatch.update(
            status="cancelled",
            history=[
                {
                    "from": "prepared",
                    "to": "cancelled",
                    "basis": "cancelled before dispatch",
                    "at": "2025-01-01T00:01:00Z",
                }
            ],
        )
        self.dump(SIDE, {"format": "lb-document-state", "documents": self.metadata})
        self.dump("lb/old.json", self.old | {"operations": []})
        preview = self.run_migration()
        self.assertEqual(preview.code, 0, preview.value)
        self.assertEqual(preview.value["send_task_mapping"], {})
        self.assertEqual(self.run_migration(token=preview.value["plan_token"]).code, 0)
        value = self.unified()
        self.assertEqual(value["execution"]["operations"], {})
        self.assertEqual(value["execution"]["tasks"], {})
        self.assertEqual(
            value["legacy_history"][THINKING]["dispatch"]["dispatch-1"], self.dispatch
        )
        self.assertEqual(
            value["legacy_history"][THINKING]["agent"],
            self.metadata[THINKING]["agent"],
        )

    def test_presend_cancellation_conflicting_with_delivery_is_refused(self):
        self.dispatch.update(
            status="cancelled",
            history=[
                {
                    "from": "prepared",
                    "to": "cancelled",
                    "basis": "cancelled before dispatch",
                    "at": "2025-01-01T00:01:00Z",
                }
            ],
        )
        self.dump(SIDE, {"format": "lb-document-state", "documents": self.metadata})
        self.assertEqual(self.run_migration().code, 4)

    def test_preserves_original_sources_and_imports_operational_send_guard(self):
        original = {
            p: (self.root / p).read_bytes()
            for p in (LOG, THINKING, SIDE, "lb/old.json")
        }
        result = self.apply()
        self.assertTrue(result.value["changed"])
        self.assertEqual(original, {p: (self.root / p).read_bytes() for p in original})
        self.assertEqual((self.root / ARCHIVE).stat().st_mode & 0o777, 0o600)
        envelope = self.unified()
        self.assertEqual(envelope["identity"]["run_id"], DOC_ID)
        self.assertEqual(
            envelope["execution"]["operations"]["send-1"],
            self.op | {"legacy_task_id": "task-build"},
        )
        self.assertTrue(load(str(self.root), LOG).markdown_authority)
        ex = envelope["execution"]
        self.assertTrue(readiness.unresolved_operation(ex, "task-build"))
        self.assertFalse(readiness.unresolved_operation(ex, "task-other"))
        with self.assertRaisesRegex(
            LbError, "Submitted delivery has no business-action"
        ):
            transport.task_send_guard(
                ex, "task-build", "new-id", {"task_id": "task-build"}
            )
        with self.assertRaisesRegex(LbError, "operation ID binds another request"):
            transport.task_send_guard(
                ex, "task-build", "send-1", {"task_id": "task-build"}
            )
        replay = self.run_migration(token=result.value["plan_token"])
        self.assertFalse(replay.value["changed"])

    def test_unknown_send_blocks_across_tasks(self):
        self.op.update(outcome="unknown", receipt=None)
        self.dump("lb/old.json", self.old)
        self.apply()
        ex = self.unified()["execution"]
        with self.assertRaisesRegex(LbError, "unknown delivery blocks"):
            transport.task_send_guard(ex, "another-task", "new-id", {})
        self.assertTrue(
            readiness.unresolved_operation(ex, "another-task", across_tasks=True)
        )

    def test_refuses_missing_mapping_and_stale_plan(self):
        dry = self.run_migration()
        self.dispatch["scope"] = "changed package"
        self.dump(SIDE, {"format": "lb-document-state", "documents": self.metadata})
        refused = self.run_migration(token=dry.value["plan_token"])
        self.assertEqual(refused.code, 4)
        self.assertIn(
            "unverified Dispatch/Task mapping", refused.value["conflicts"][0]["message"]
        )
        self.assertFalse((self.root / ARCHIVE).exists())
        self.dispatch["scope"] = "example scope"
        self.dump(SIDE, {"format": "lb-document-state", "documents": self.metadata})
        (self.root / THINKING).write_text("# Edited Thinking\n")
        with self.assertRaisesRegex(LbError, "plan token differs"):
            self.run_migration(token=dry.value["plan_token"])
        self.assertFalse((self.root / TARGET).exists())

    def test_rollback_is_atomic_repeatable_and_retires_the_apply_token(self):
        original_sha = (self.root / SIDE).read_bytes()
        result = self.apply()
        selected = self.run_migration(rollback=True)
        token = selected.value["rollback_token"]
        with self.assertRaisesRegex(LbError, "plan token differs"):
            self.run_migration(token=result.value["plan_token"], rollback=True)
        finished = self.run_migration(token=token, rollback=True)
        self.assertEqual(finished.value["status"], "rolled_back")
        self.assertFalse(load(str(self.root), LOG).markdown_authority)
        self.assertEqual((self.root / SIDE).read_bytes(), original_sha)
        self.assertFalse(
            self.run_migration(token=token, rollback=True).value["changed"]
        )
        with self.assertRaisesRegex(LbError, "was rolled back"):
            self.run_migration(token=result.value["plan_token"])

    def test_rollback_refuses_subsequent_markdown_and_runtime_writes(self):
        self.apply()
        expected = self.run_migration(rollback=True).value["rollback_token"]
        old = (self.root / THINKING).read_text()
        self.dump(THINKING, old + "Later evidence\n")
        with self.assertRaisesRegex(LbError, "migration source changed"):
            self.run_migration(token=expected, rollback=True)
        self.dump(THINKING, old)
        fact = {
            "id": "action-1",
            "kind": "business-action",
            "operation_id": "send-1",
            "outcome": "started",
            "source": {"kind": "runtime_observation", "ref": "example review"},
        }
        self.dump("fact.json", {"facts": [fact]})
        context = execution_service.context(str(self.root), LOG).value
        execution_service.record(
            str(self.root), LOG, "fact.json", context["version_token"], False
        )
        with self.assertRaisesRegex(LbError, "state changed since cutover"):
            self.run_migration(token=expected, rollback=True)
        self.assertTrue(load(str(self.root), LOG).markdown_authority)

    def test_prepared_backup_recovers_after_failure_before_target_publish(self):
        token = self.run_migration().value["plan_token"]

        def interrupt(fd, name, data, before):
            if name == "migrated.json":
                raise OSError("synthetic interruption")
            replace_bytes_at(fd, name, data, before)

        with patch(
            "logbook_cli.legacy_migration.replace_bytes_at", side_effect=interrupt
        ):
            with self.assertRaisesRegex(LbError, "synthetic interruption"):
                self.run_migration(token=token)
        self.assertTrue((self.root / ARCHIVE).exists())
        self.assertFalse(load(str(self.root), LOG).markdown_authority)
        self.assertTrue(self.run_migration(token=token).value["changed"])
        self.assertTrue(load(str(self.root), LOG).markdown_authority)

    def test_migration_state_decoder_refuses_malformed_and_overdeep_json(self):
        for data in (b'{"duplicate":0,"duplicate":1}', b"\xff", b"[" * 100_000 + b"]" * 100_000):
            with self.subTest(sample=data[:24]):
                with self.assertRaisesRegex(LbError, "invalid migration state") as refusal:
                    legacy_migration.load_json(data)
                self.assertEqual(refusal.exception.code, 4)

    def test_apply_rechecks_renamed_sidecar_before_publication(self):
        base, project, _, request = legacy_migration.scope(str(self.root), LOG, "migrated", [])
        result, archive = legacy_migration.prepare(base, project, "migrated", request)
        self.assertEqual(result.code, 0)
        retained = self.dump(
            "lb/retained.json",
            {"format": "lb-document-state", "documents": {
                THINKING: {"document": self.identity("4" * 32)}
            }},
        )
        sources = {path: path.read_bytes() for path in (
            self.root / LOG, self.root / THINKING, self.root / SIDE, self.root / "lb/old.json",
            retained,
        )}
        with self.assertRaisesRegex(LbError, "wrong sidecar"):
            self.run_migration(token=archive["plan_token"])
        for path in (TARGET, ARCHIVE, "lb/migrated.migration-done"):
            self.assertFalse((self.root / path).exists())
        self.assertEqual(sources, {path: path.read_bytes() for path in sources})

    def test_unpublished_migration_rechecks_renamed_sidecar_before_receipt(self):
        base, project, _, request = legacy_migration.scope(str(self.root), LOG, "migrated", [])
        result, archive = legacy_migration.prepare(base, project, "migrated", request)
        self.assertEqual(result.code, 0)
        target = self.root / TARGET
        backup = self.root / ARCHIVE
        target.write_bytes(unified.encode(legacy_migration.initial_candidate(archive)))
        backup.write_bytes(unified.encode(archive))
        retained = self.dump(
            "lb/retained.json",
            {"format": "lb-document-state", "documents": {
                LOG: {"document": self.identity("4" * 32)}
            }},
        )
        sources = {path: path.read_bytes() for path in (target, backup, retained)}
        with self.assertRaisesRegex(LbError, "wrong sidecar"):
            self.run_migration(token=archive["plan_token"])
        self.assertFalse(target.with_suffix(".migration-done").exists())
        self.assertEqual(sources, {path: path.read_bytes() for path in sources})

    def test_held_writer_and_stale_legacy_document_refuse_changes(self):
        token = self.run_migration().value["plan_token"]
        stale = load(str(self.root), LOG)
        lock = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(LbError, "migration_busy"):
                self.run_migration(token=token)
        finally:
            os.close(lock)
        self.assertFalse((self.root / ARCHIVE).exists())
        self.run_migration(token=token)
        with self.assertRaisesRegex(LbError, "document authority changed"):
            write_bytes(stale, stale.data + b"stale edit\n", False)
        with self.assertRaisesRegex(LbError, "monitoring authority changed"):
            observation.scope(stale)

    def test_unknown_send_reconciles_by_attributed_evidence_and_keeps_request(self):
        self.op.update(outcome="unknown", receipt=None)
        self.op["request"]["task_id"] = "task-build"
        self.dump("lb/old.json", self.old)
        self.apply()
        fact = {
            "id": "resolution-1",
            "kind": "transport-resolution",
            "operation_id": "send-1",
            "outcome": "submitted",
            "source": {"kind": "runtime_observation", "ref": "verified submission"},
        }
        self.dump("fact.json", {"facts": [fact]})
        context = execution_service.context(str(self.root), LOG).value
        execution_service.record(
            str(self.root), LOG, "fact.json", context["version_token"], False
        )
        context = execution_service.context(str(self.root), LOG).value
        op = context["state"]["operations"][0]
        self.assertEqual(op["request"], self.op["request"])
        self.assertEqual(op["receipt"], {"evidence_ref": "verified submission"})
        self.assertEqual(op["outcome"], "submitted")
        self.assertTrue(
            readiness.unresolved_operation(self.unified()["execution"], "task-build")
        )

    def test_lost_imported_operation_fails_closed(self):
        self.apply()
        changed = self.unified()
        changed["execution"]["operations"].clear()
        unified.publish(self.root / TARGET, changed)
        with self.assertRaisesRegex(LbError, "retained legacy operation changed"):
            load(str(self.root), LOG)

    def test_legacy_attempt_and_unmatched_operation_refuse_clearance(self):
        self.dispatch["attempts"] = [{"id": "attempt-1", "status": "started"}]
        self.dump(SIDE, {"format": "lb-document-state", "documents": self.metadata})
        result = self.run_migration()
        self.assertEqual(result.code, 4)
        self.assertNotIn("plan_token", result.value)
        self.assertIn("unsupported attempts", result.value["conflicts"][0]["message"])

    def test_committed_missing_target_fences_legacy_and_alternate_destination(self):
        plan = self.apply().value["plan_token"]
        (self.root / TARGET).unlink()
        with self.assertRaisesRegex(LbError, "legacy authority remains fenced"):
            load(str(self.root), LOG)
        with self.assertRaisesRegex(LbError, "legacy authority remains fenced"):
            self.run_migration(token=plan)
        with self.assertRaisesRegex(LbError, "legacy authority remains fenced"):
            legacy_migration.run(
                str(self.root),
                LOG,
                "other",
                [],
                dry_run=True,
                is_rollback=False,
                token=None,
            )

    def test_unbacked_captain_marker_cannot_lose_its_legacy_guard(self):
        (self.root / "lb/old.json").unlink()
        self.metadata[THINKING].pop("agent")
        self.metadata[THINKING].pop("dispatch")
        self.dump(SIDE, {"format": "lb-document-state", "documents": self.metadata})
        log = (self.root / LOG).read_text()
        self.dump(LOG, log + "    - Status: 👨‍✈️ Taking over\n")
        result = legacy_migration.run(
            str(self.root),
            LOG,
            "migrated",
            [THINKING],
            dry_run=True,
            is_rollback=False,
            token=None,
        )
        self.assertEqual(result.code, 4)
        self.assertIn("Captain marker", result.value["conflicts"][0]["message"])
        self.assertNotIn("plan_token", result.value)
