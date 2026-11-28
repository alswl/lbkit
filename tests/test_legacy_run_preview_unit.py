"""Unit tests for legacy ownership detection and read-only migration plans."""

import fcntl
import hashlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from herdr_fixtures import target as observation_target

from logbook_cli import execution, legacy_run, unified, wait_state
from logbook_cli.document import LbError
from logbook_cli.services import agent_wait

DOC_ID = "1" * 32
THINKING_ID = "2" * 32
OBS_ID = "3" * 32
OTHER_ID = "4" * 32
OBSERVATION_PATH = f"lb/observations/{DOC_ID}.json"


class LegacyRunPreviewTest(TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.log = self.root / "docs/delivery.md"
        self.write("docs/delivery.md", "# Sample delivery\n")
        self.write("thinking/delivery.md", "# Sample thinking\n")
        self.record = {
            "name": "old-run",
            "log": "docs/delivery.md",
            "thinking": "thinking/delivery.md",
            "advancement": "sample",
            "captain": "captain-example",
            "facts": [],
            "operations": [],
        }

    def write(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value if isinstance(value, str) else json.dumps(value))
        return path

    def test_init_refuses_bound_execution_independently_of_destination(self):
        self.write("lb/old-run.json", self.record)
        for name in ("old-run", "different"):
            with self.subTest(name=name):
                with self.assertRaisesRegex(LbError, "old execution layout conflict"):
                    unified.initialize(self.root, self.log, name, [], dry_run=True)

    def test_execution_lookup_finds_legacy_record_named_markdown(self):
        record = self.record | {"name": "history.markdown"}
        source = self.write("lb/history.markdown.json", record)
        self.sidecar({"docs/archive.markdown": OTHER_ID}, name="archive.markdown-sidecar").rename(
            self.root / "lb/archive.markdown.json"
        )

        path, raw, found = execution.find_legacy(self.root, self.log)

        self.assertEqual(path, source)
        self.assertEqual(raw, source.read_bytes())
        self.assertEqual(found, record)

    def preview(self, *documents, name="new-run"):
        return legacy_run.preview(str(self.root), "docs/delivery.md", name, documents)

    def sidecar(self, sections=None, name="delivery"):
        if sections is None:
            sections = {"docs/delivery.md": DOC_ID, "thinking/delivery.md": THINKING_ID}
        return self.write(
            f"lb/{name}.md.json",
            {
                "format": "lb-document-state",
                "documents": {
                    relative: {
                        "document": {"identity": {"id": "identity", "uuid": uuid}}
                    }
                    for relative, uuid in sections.items()
                },
            },
        )

    def monitoring(self, status="ended"):
        target = observation_target()
        binding = target["binding"]
        digest = hashlib.sha256(agent_wait.encoded(binding)).hexdigest()
        key = f"{OBS_ID}:{digest}:question-1"
        event = {"binding": binding, "kind": "needs_input", "event_id": "question-1"}
        return {
            "format": "lb-observation",
            "id": OBS_ID,
            "revision": 7,
            "targets": [target],
            "cursors": [wait_state.initial(target)],
            "events": [
                {"id": key, "observation": event, "handling": "deferred", "history": []}
            ],
            "answers": [
                {
                    "id": "answer-1",
                    "event_id": key,
                    "binding": binding,
                    "status": "unknown",
                    "history": [],
                }
            ],
            "listener": {
                "invocation_id": "listener-1",
                "generation": 2,
                "status": status,
            },
        }

    def operation(self, key, outcome):
        return {
            "id": key,
            "request": {
                "dispatch_id": f"dispatch-{key}",
                "recipient": "agent-example",
                "session_id": "session-example",
                "binding_digest": "1" * 64,
                "message_digest": "2" * 64,
                "package_digest": "3" * 64,
            },
            "outcome": outcome,
            "receipt": {"accepted": True} if outcome == "submitted" else None,
            "provenance": "adapter",
        }

    def tree(self):
        return {
            path.relative_to(self.root): path.read_bytes() if path.is_file() else None
            for path in self.root.rglob("*")
        }

    def test_fresh_init_ignores_execution_for_a_different_log(self):
        self.write("docs/another.md", "# Another sample\n")
        self.write("lb/old-run.json", self.record | {"log": "docs/another.md"})
        value = unified.initialize(self.root, self.log, "different", [], dry_run=True)
        self.assertTrue(value["changed"])
        self.assertFalse((self.root / "lb/.lock").exists())

    def test_preview_lists_history_without_writes_or_transport(self):
        self.sidecar()
        self.record["facts"] = [
            {
                "id": "takeover-1",
                "kind": "takeover",
                "origin": "explicit",
                "source": {"kind": "human_instruction", "ref": "example instruction"},
                "release_condition": None,
            }
        ]
        self.record["operations"] = [
            self.operation("send-1", "submitted"),
            self.operation("send-2", "unknown"),
            self.operation("send-3", "not_submitted"),
        ]
        self.write("lb/old-run.json", self.record)
        monitor = self.monitoring()
        self.write(OBSERVATION_PATH, monitor)
        self.write(f"lb/observations/{OTHER_ID}.json", {"unrelated": True})
        before = self.tree()
        with (
            patch("subprocess.Popen", side_effect=AssertionError("spawned process")),
            patch(
                "logbook_cli.unified.publish",
                side_effect=AssertionError("published state"),
            ),
        ):
            result = self.preview()
        self.assertEqual(result.code, 0)
        self.assertEqual(before, self.tree())
        value = result.value
        self.assertFalse(value["apply_available"])
        self.assertNotIn("state", value)
        self.assertNotIn("version_token", value)
        self.assertEqual(value["target"], "lb/new-run.json")
        self.assertEqual(
            value["identity"],
            {
                "log_path": "docs/delivery.md",
                "document_paths": ["docs/delivery.md", "thinking/delivery.md"],
                "document_uuids": {
                    "docs/delivery.md": DOC_ID,
                    "thinking/delivery.md": THINKING_ID,
                },
                "proposed_run_id": DOC_ID,
            },
        )
        sources = value["sources"]
        self.assertEqual(sources["sidecars"][0]["path"], "lb/delivery.md.json")
        self.assertEqual(sources["execution"]["captain"], "captain-example")
        self.assertTrue(sources["execution"]["delegation_restricted"])
        self.assertEqual(
            sources["execution"]["facts"], [{"id": "takeover-1", "kind": "takeover"}]
        )
        self.assertEqual(
            [
                (row["id"], row["outcome"], row["has_receipt"])
                for row in sources["execution"]["operations"]
            ],
            [
                ("send-1", "submitted", True),
                ("send-2", "unknown", False),
                ("send-3", "not_submitted", False),
            ],
        )
        self.assertEqual(sources["monitoring"]["path"], OBSERVATION_PATH)
        event_id = monitor["events"][0]["id"]
        self.assertEqual(
            sources["monitoring"]["unresolved_events"],
            [{"id": event_id, "handling": "deferred"}],
        )
        self.assertEqual(
            sources["monitoring"]["pending_answers"],
            [{"id": "answer-1", "status": "unknown", "event_id": event_id}],
        )

    def test_execution_only_preview_does_not_invent_run_id(self):
        self.write("lb/old-run.json", self.record)
        result = self.preview()
        self.assertEqual(result.code, 0)
        value = result.value
        self.assertIsNone(value["identity"]["proposed_run_id"])
        self.assertIsNone(value["sources"]["monitoring"])

    def test_preview_keeps_unselected_sections_out_of_inventory(self):
        self.sidecar()
        result = self.preview()
        self.assertEqual(result.code, 0)
        row = result.value["sources"]["sidecars"][0]
        self.assertEqual(row["documents"], ["docs/delivery.md"])
        self.assertEqual(row["unselected_sections"], 1)

    def test_existing_file_at_target_is_a_conflict(self):
        self.write("lb/old-run.json", self.record)
        self.write("lb/existing.json", {"example": "already here"})
        for name, code in (
            ("old-run", "target_is_legacy_execution"),
            ("existing", "target_exists"),
        ):
            with self.subTest(name=name):
                result = self.preview(name=name)
                self.assertEqual(result.code, 4)
                self.assertEqual(result.value["conflicts"][0]["code"], code)

    def test_reports_legacy_document_and_execution_journals(self):
        self.write("lb/old-run.json", self.record)
        for path in ("lb/delivery.md.transaction", "lb/old-run.json.transaction"):
            self.write(path, "pending hypothetical write")
        before = self.tree()
        result = self.preview()
        self.assertEqual(result.code, 4)
        self.assertEqual(
            result.value["conflicts"],
            [
                {"code": "legacy_transaction", "path": "lb/delivery.md.transaction"},
                {"code": "legacy_transaction", "path": "lb/old-run.json.transaction"},
            ],
        )
        self.assertEqual(self.tree(), before)

    def test_reports_saved_listener_and_live_lock_separately(self):
        self.sidecar()
        self.write(OBSERVATION_PATH, self.monitoring("active"))
        listener = self.write(f"lb/observations/{DOC_ID}.listener", "")
        action = self.write(f"lb/observations/{DOC_ID}.action-example", "")
        with listener.open("rb") as listener_handle, action.open("rb") as action_handle:
            for handle in (listener_handle, action_handle):
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = self.preview()
        self.assertEqual(result.code, 4)
        self.assertEqual(
            [row["code"] for row in result.value["conflicts"]],
            [
                "listener_busy",
                "action_busy",
                "saved_listener_active",
            ],
        )
        result = self.preview()
        self.assertEqual(
            [row["code"] for row in result.value["conflicts"]],
            ["saved_listener_active"],
        )

    def test_rejects_two_execution_records_bound_to_same_log(self):
        self.write("lb/old-run.json", self.record)
        self.write("lb/other.json", self.record | {"name": "other"})
        with self.assertRaisesRegex(LbError, "multiple execution states"):
            self.preview()

    def test_rejects_execution_with_a_traversing_binding(self):
        self.write("lb/old-run.json", self.record | {"log": "docs/../docs/delivery.md"})
        with self.assertRaisesRegex(LbError, "invalid execution document binding"):
            self.preview()
        with self.assertRaisesRegex(LbError, "invalid execution document binding"):
            unified.initialize(self.root, self.log, "different", [], dry_run=True)

    def test_rejects_execution_with_a_symlink_binding(self):
        (self.root / "docs/alias.md").symlink_to(self.log)
        self.write("lb/old-run.json", self.record | {"log": "docs/alias.md"})
        with self.assertRaisesRegex(LbError, "invalid execution state"):
            unified.initialize(self.root, self.log, "different", [], dry_run=True)

    def test_rejects_explicit_document_owned_by_another_execution(self):
        self.write("lb/old-run.json", self.record)
        self.write("docs/other.md", "# Another log\n")
        self.write("thinking/other.md", "# Other thinking\n")
        self.write(
            "lb/other.json",
            self.record
            | {
                "name": "other",
                "log": "docs/other.md",
                "thinking": "thinking/other.md",
            },
        )
        with self.assertRaisesRegex(LbError, "another legacy execution"):
            self.preview("thinking/other.md")

    def test_rejects_misfiled_sidecar_and_duplicate_uuid(self):
        self.sidecar(name="wrong")
        with self.assertRaisesRegex(LbError, "wrong sidecar"):
            self.preview()
        (self.root / "lb/wrong.md.json").unlink()
        self.sidecar()
        self.sidecar({"docs/other.md": DOC_ID}, name="other")
        with self.assertRaisesRegex(LbError, "UUID has multiple owners"):
            self.preview()

    def test_preview_refuses_renamed_sidecar_bound_to_a_selected_document(self):
        self.sidecar()
        self.assertEqual(self.preview("thinking/delivery.md").code, 0)
        for relative in ("docs/delivery.md", "thinking/delivery.md"):
            with self.subTest(relative=relative):
                self.sidecar({relative: OTHER_ID}, name="retained").rename(
                    self.root / "lb/retained.json"
                )
                before = self.tree()
                with self.assertRaisesRegex(LbError, "wrong sidecar"):
                    self.preview("thinking/delivery.md")
                self.assertEqual(self.tree(), before)

    def test_rejects_path_fallback_observation_and_ignores_unowned_uuid_file(self):
        self.write(f"lb/observations/{OTHER_ID}.json", self.monitoring())
        with self.assertRaisesRegex(LbError, "no legacy sources"):
            self.preview()
        self.write("lb/observations/docs/delivery.md.json", self.monitoring())
        with self.assertRaisesRegex(LbError, "verified document UUID"):
            self.preview()

    def test_rejects_bad_event_and_answer_ownership(self):
        self.sidecar()
        monitor = self.monitoring()
        monitor["events"][0]["id"] = "wrong"
        self.write(OBSERVATION_PATH, monitor)
        with self.assertRaisesRegex(LbError, "Event identity"):
            self.preview()
        monitor = self.monitoring()
        monitor["answers"][0]["event_id"] = "wrong"
        self.write(OBSERVATION_PATH, monitor)
        with self.assertRaisesRegex(LbError, "Answer ownership"):
            self.preview()

    def test_rejects_selected_symlink_fifo_and_cross_project_document(self):
        self.sidecar()
        obs_path = self.root / OBSERVATION_PATH
        obs_path.parent.mkdir()
        obs_path.symlink_to(self.root / "missing.json")
        with self.assertRaisesRegex(LbError, "invalid legacy observation"):
            self.preview()
        obs_path.unlink()
        os.mkfifo(obs_path)
        with self.assertRaisesRegex(LbError, "expected a regular file"):
            self.preview()
        obs_path.unlink()
        self.write("other/mind.yaml", "{}")
        self.write("other/docs/delivery.md", "# Another sample\n")
        with self.assertRaisesRegex(LbError, "--document.*outside the Logbook project"):
            self.preview("other/docs/delivery.md")

    def test_other_unified_run_cannot_share_the_proposed_identity(self):
        other_log = self.write("docs/other.md", "# Another log\n")
        value = unified.initialize(self.root, other_log, "another", [], dry_run=True)
        envelope = value["state"]
        envelope["identity"]["run_id"] = DOC_ID
        self.write("lb/another.json", envelope)
        self.sidecar()
        with self.assertRaisesRegex(LbError, "legacy run UUID is already in use"):
            self.preview()

    def test_reports_observation_for_an_associated_document_as_conflict(self):
        self.sidecar()
        relative = f"lb/observations/{THINKING_ID}.json"
        self.write(relative, self.monitoring())
        result = self.preview("thinking/delivery.md")
        self.assertEqual(result.code, 4)
        self.assertIsNone(result.value["sources"]["monitoring"])
        self.assertEqual(
            result.value["conflicts"],
            [
                {"code": "associated_document_observation", "path": relative},
            ],
        )

    def test_unsafe_destination_and_held_writer_cannot_clear_preview(self):
        self.sidecar()
        target = self.root / "lb/new-run.json"
        target.symlink_to(self.root / "missing.json")
        with self.assertRaises(LbError):
            self.preview()
        target.unlink()
        with self.write("lb/.lock", "").open("rb") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = self.preview()
        self.assertEqual(result.code, 4)
        self.assertEqual(
            result.value["conflicts"],
            [
                {"code": "writer_busy", "path": "lb/.lock"},
            ],
        )

    def test_reports_held_legacy_document_writer(self):
        self.sidecar()
        fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = self.preview()
        finally:
            os.close(fd)
        self.assertEqual(result.code, 4)
        self.assertEqual(
            result.value["conflicts"], [{"code": "legacy_writer_busy", "path": "."}]
        )
