"""Markdown is readable; machine facts share the existing mind state and CAS."""

import hashlib
import json
from unittest.mock import patch

from coordination_helpers import CoordinationTest

from logbook_cli import storage
from logbook_cli.document import parse
from logbook_cli.services import task_lifecycle
from logbook_cli.state import journal_for


class TaskRecordBoundaryTest(CoordinationTest):
    def state(self):
        return json.loads((self.root / "lb/log.md.json").read_text())

    def legacy(self, identified=True):
        if identified:
            self.identify()
        value = {
            "task": hashlib.sha256(b"Correct typo").hexdigest(),
            "as": "human-cancelled",
            "decision": "取消依据 [决定](https://example.org/decision)",
            "note": "保留历史证据",
        }
        self.log.write_text(
            self.log.read_text().replace("- [ ]", "- [-]")
            + "    - Resolution: "
            + json.dumps(value)
            + "\n"
        )
        return value

    def migrate(self, *args, token=None, code=0):
        return self.cli(
            "task",
            "migrate",
            "log.md",
            "--expect-version",
            token or self.token(),
            *args,
            code=code,
        )

    def test_cancel_preview_apply_reopen_and_history(self):
        self.identify()
        before = self.snapshot()
        preview = self.action(
            "cancel", "T1", "--basis", "取消：依据 example", "--dry-run"
        )
        self.assertEqual(before, self.snapshot())
        self.assertIn("lb/log.md.json", preview["diff"])
        self.action("cancel", "T1", "--basis", "取消：依据 example")
        text = self.log.read_text()
        self.assertIn("取消：依据 example", text)
        self.assertNotIn("Resolution: {", text)
        self.assertNotIn(hashlib.sha256(b"Correct typo").hexdigest(), text)
        self.assertEqual(self.show()["status"], "cancelled")
        resolution = self.show()["resolution"]
        self.action("reopen")
        self.assertEqual(self.show()["status"], "active")
        self.assertNotIn("resolution", self.show())
        self.assertIn("Historical disposition: cancelled", self.log.read_text())
        self.assertEqual(
            self.show()["history"][-1]["previous_record"]["resolution"], resolution
        )
        self.action("cancel", "T1", "--basis", "Second decision")
        self.assertIn("取消：依据 example", self.log.read_text())

    def test_inline_migration_preserves_identity_exact_evidence_and_prose(self):
        for identified in (True, False):
            with self.subTest(identified=identified):
                # Each form gets an independent disposable document/state pair.
                self.log.write_text(
                    "# Example\n\n## Stage 01 Build\n\n- [ ] Correct typo\n"
                )
                (self.root / "lb/log.md.json").unlink(missing_ok=True)
                legacy = self.legacy(identified)
                before = self.snapshot()
                self.migrate("--dry-run")
                self.assertEqual(before, self.snapshot())
                if identified:
                    self.action("reopen", code=4)
                self.migrate()
                tasks = self.state()["documents"]["log.md"]["task"]
                task_id = next(iter(tasks))
                if identified:
                    self.assertEqual(task_id, "T1")
                self.assertEqual(tasks[task_id]["resolution"], legacy)
                self.assertIn(
                    json.dumps(legacy),
                    tasks[task_id]["history"][-1]["inline_annotations"][0],
                )
                self.assertIn("取消依据", self.log.read_text())
                self.assertNotIn("\\u", self.log.read_text())
                self.action("reopen", task_id)
                self.assertIn("保留历史证据", self.log.read_text())
                self.assertIn(
                    "保留历史证据", json.dumps(self.show(task_id), ensure_ascii=False)
                )

    def test_resume_is_machine_state_and_blocker_remains_readable(self):
        self.identify()
        self.action("block", "T1", "--reason", "Need evidence")
        self.action("pause")
        self.assertNotIn("Resume:", self.log.read_text())
        self.assertEqual(self.show()["resume"], "pending")
        self.assertIn("Blocker: Need evidence", self.log.read_text())
        self.action("resume")
        self.assertEqual(self.show()["status"], "blocked")
        self.assertNotIn("resume", self.show())

    def test_legacy_resume_migration_and_conflict(self):
        self.identify()
        self.log.write_text(
            self.log.read_text().replace("- [ ]", "- [!]") + "    - Resume: pending\n"
        )
        self.action("resume", code=4)
        self.migrate()
        self.assertEqual(self.show()["resume"], "pending")
        self.log.write_text(self.log.read_text() + "    - Resume: active\n")
        # Context may refuse inconsistent records; use a token from the parsed pair.
        token = parse(self.log, self.root).token
        before = self.snapshot()
        self.migrate(token=token, code=4)
        self.assertEqual(before, self.snapshot())

    def test_stale_duplicate_and_missing_records_refuse_without_writes(self):
        self.identify()
        self.action("cancel")
        good = self.snapshot()
        for change in ("text", "duplicate", "missing", "projection"):
            with self.subTest(change=change):
                for name, data in good.items():
                    (self.root / name).write_bytes(data)
                if change == "missing":
                    (self.root / "lb/log.md.json").unlink()
                elif change == "text":
                    self.log.write_text(
                        self.log.read_text().replace("Correct typo", "Different task")
                    )
                elif change == "duplicate":
                    self.log.write_text(self.log.read_text() + "    - Resolution: {}\n")
                else:
                    self.log.write_text(
                        self.log.read_text().replace(
                            "Authorized work", "Different decision"
                        )
                    )
                token = parse(self.log, self.root).token
                before = self.snapshot()
                self.action("reopen", token=token, code=4)
                self.assertEqual(before, self.snapshot())

    def test_migration_stale_digest_refuses(self):
        self.legacy(False)
        self.log.write_text(self.log.read_text().replace("Correct typo", "Changed"))
        before = self.snapshot()
        self.migrate(code=4)
        self.assertEqual(before, self.snapshot())

    def test_state_only_concurrent_change_invalidates_cancel_token(self):
        self.identify()
        token = self.token()
        state = self.state()
        state["documents"]["log.md"]["task"]["T1"]["basis"] = "Concurrent update"
        (self.root / "lb/log.md.json").write_text(json.dumps(state))
        before = self.snapshot()
        self.action("cancel", token=token, code=4)
        self.assertEqual(before, self.snapshot())

    def test_cancel_interruption_recovers_both_files(self):
        self.identify()
        original = storage._replace
        count = 0

        def interrupted(*args, **kwargs):
            nonlocal count
            count += 1
            if count == 2:
                raise OSError("simulated interruption")
            return original(*args, **kwargs)

        with patch.object(storage, "_replace", side_effect=interrupted):
            with self.assertRaises(OSError):
                task_lifecycle.semantic_transition(
                    str(self.root),
                    "log.md",
                    "T1",
                    "cancel",
                    "Authorized decision",
                    self.token(),
                    False,
                )
        self.assertTrue(journal_for(self.log, self.root).exists())
        preview = self.cli("log", "recover", "log.md", "--dry-run")
        self.cli(
            "log", "recover", "log.md", "--expect-version", preview["version_token"]
        )
        self.assertEqual(self.show()["status"], "cancelled")
        self.assertIn("Authorized decision", self.log.read_text())

    def test_note_cannot_reintroduce_inline_machine_records(self):
        self.identify()
        before = self.snapshot()
        self.cli(
            "task",
            "note",
            "log.md",
            "--stage",
            "Stage 01 Build",
            "--task",
            "Correct typo",
            "--text",
            "Resume: pending",
            "--expect-version",
            self.token(),
            code=4,
        )
        self.assertEqual(before, self.snapshot())

    def test_duplicate_json_keys_are_not_accepted_by_legacy_reader(self):
        self.legacy(False)
        self.log.write_text(
            self.log.read_text().replace(
                '"as": "human-cancelled"',
                '"as": "not-applicable", "as": "human-cancelled"',
            )
        )
        before = self.snapshot()
        self.assertIsNone(self.context()["stages"][0]["tasks"][0]["resolution"])
        self.migrate(code=4)
        self.assertEqual(before, self.snapshot())

    def test_legacy_status_cancel_also_uses_external_records(self):
        self.identify()
        state = self.state()
        state["documents"]["log.md"]["task"]["T1"]["status"] = "pending"
        (self.root / "lb/log.md.json").write_text(json.dumps(state))
        self.action("cancel")
        item = self.show()
        self.assertEqual(item["resolution"]["as"], "cancelled")
        self.assertNotIn("Resolution: {", self.log.read_text())
        self.assertEqual(item["history"][0]["status"], "pending")
        self.action("reopen")
        self.assertIn("Authorized work", self.log.read_text())

    def test_invalid_external_attribution_does_not_settle_task(self):
        self.identify()
        self.action("cancel")
        state = self.state()
        del state["documents"]["log.md"]["task"]["T1"]["resolution"]["actor"]
        (self.root / "lb/log.md.json").write_text(json.dumps(state))
        before = self.snapshot()
        self.assertIsNone(self.context()["stages"][0]["tasks"][0]["resolution"])
        self.action("reopen", code=4)
        self.assertEqual(before, self.snapshot())

    def test_resume_explicit_destination_cannot_override_recorded_state(self):
        self.identify()
        self.action("pause")
        before = self.snapshot()
        self.action("resume", "T1", "--to", "active", code=4)
        self.assertEqual(before, self.snapshot())
        self.action("resume", "T1", "--to", "pending")
        self.assertEqual(self.show()["status"], "pending")

    def test_identified_split_keeps_readable_decision_and_archived_identity(self):
        self.identify()
        request = {
            "task_id": "T1",
            "replacements": [
                {"id": "T2", "text": "Heading"},
                {"id": "T3", "text": "Paragraph"},
            ],
            "reference_changes": {},
        }
        (self.root / "split.json").write_text(json.dumps(request))
        self.cli(
            "task",
            "split",
            "log.md",
            "--input-file",
            "split.json",
            "--decision",
            "Approved scope [decision](https://example.org/decision)",
            "--expect-version",
            self.token(),
        )
        self.assertIn("Split from T1: Correct typo", self.log.read_text())
        self.assertIn("[decision](https://example.org/decision)", self.log.read_text())
        archive = self.state()["documents"]["log.md"]["task-archive"]["T1"]
        self.assertEqual(archive["previous_text"], "Correct typo")
        self.assertIn("<!-- lb-task T1 -->", archive["content"])
