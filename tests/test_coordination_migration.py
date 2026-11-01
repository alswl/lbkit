"""Migration contracts: explicit preview, CAS apply, no guessed legacy meaning."""

import json
from unittest.mock import patch

from coordination_helpers import FIXTURES, CoordinationTest

from logbook_cli import records, storage
from logbook_cli.document import parse
from logbook_cli.state import journal_for


class CoordinationMigrationTest(CoordinationTest):
    def legacy(self, name="legacy.json", ambiguous=False):
        self.fixture("legacy.md")
        state = json.loads((FIXTURES / name).read_text())
        if not ambiguous:
            del state["documents"]["log.md"]["task"]["T3"]
            self.log.write_text(self.log.read_text().split("- [-]")[0])
        (self.root / "lb").mkdir(exist_ok=True)
        (self.root / "lb/log.md.json").write_text(json.dumps(state))

    def migrate(self, *args, code=0, token=None):
        return self.cli(
            "task",
            "migrate",
            "log.md",
            "--expect-version",
            token or self.token(),
            *args,
            code=code,
        )

    def test_preview_then_apply_preserves_history_and_removes_duplicate_state(self):
        self.legacy()
        before = self.snapshot()
        token = self.token()
        self.migrate("--dry-run")
        self.assertEqual(before, self.snapshot())
        self.migrate(token=token)
        self.assertEqual(self.show("T1")["status"], "done")
        self.assertEqual(self.show("T2")["status"], "active")
        self.assertIn("example-b", json.dumps(self.show("T2")))
        state = json.loads((self.root / "lb/log.md.json").read_text())
        for item in state["documents"]["log.md"].get("task", {}).values():
            self.assertNotIn(
                "status", item, "Current status must have one canonical source"
            )
        after = self.snapshot()
        self.migrate("--dry-run")
        self.assertEqual(after, self.snapshot())

    def test_conflicting_or_ambiguous_legacy_data_refuses_without_writes(self):
        for name, ambiguous in [("conflict.json", False), ("legacy.json", True)]:
            with self.subTest(name=name):
                self.legacy(name, ambiguous)
                before = self.snapshot()
                self.migrate(code=4)
                self.assertEqual(before, self.snapshot())

    def test_migration_apply_uses_composite_cas(self):
        self.legacy()
        token = self.token()
        state_path = self.root / "lb/log.md.json"
        value = json.loads(state_path.read_text())
        value["documents"]["log.md"]["task"]["T2"]["basis"] = "Later observation"
        state_path.write_text(json.dumps(value))
        before = self.snapshot()
        self.migrate(token=token, code=4)
        self.assertEqual(before, self.snapshot())

    def test_dependency_cycle_refuses_entire_migration(self):
        self.legacy()
        path = self.root / "lb/log.md.json"
        state = json.loads(path.read_text())
        tasks = state["documents"]["log.md"]["task"]
        tasks["T1"]["depends_on"] = ["T2"]
        tasks["T2"]["depends_on"] = ["T1"]
        path.write_text(json.dumps(state))
        before = self.snapshot()
        self.migrate(code=4)
        self.assertEqual(before, self.snapshot())

    def test_legacy_skip_is_not_guessed_as_cancelled(self):
        self.log.write_text("# Example\n\n## Stage 01 Build\n\n- [-] Old skip\n")
        before = self.snapshot()
        task = self.context()["stages"][0]["tasks"][0]
        self.assertIsNone(task["resolution"])
        self.assertEqual(before, self.snapshot())

    def legacy_dependencies(self, with_status=True):
        self.identify()
        self.log.write_text(self.log.read_text() + "- [ ] Verify\n")
        self.identify("Verify", "T2")
        path = self.root / "lb/log.md.json"
        value = json.loads(path.read_text())
        tasks = value["documents"]["log.md"]["task"]
        if with_status:
            for item in tasks.values():
                item["status"] = "pending"
        tasks["T2"]["depends_on"] = ["T1"]
        path.write_text(json.dumps(value))

    def test_legacy_dependency_remains_visible_and_prevents_early_start(self):
        self.legacy_dependencies()
        before = self.snapshot()
        self.assertEqual(self.show("T2")["depends_on"], ["T1"])
        self.action("start", "T2", code=4)
        self.assertEqual(before, self.snapshot())
        self.migrate()
        self.action("complete", "T1")
        self.action("start", "T2")
        self.assertEqual(self.show("T2")["status"], "active")

    def test_semantic_write_requires_migration_before_legacy_fact_removal(self):
        self.legacy_dependencies()
        before = self.snapshot()
        result = self.action("pause", "T2", code=4)
        self.assertIn("migrat", result.stderr)
        self.assertEqual(before, self.snapshot())
        self.migrate()
        self.action("pause", "T2")
        self.action("resume", "T2")
        self.assertEqual(self.show("T2")["depends_on"], ["T1"])

    def test_migration_recovers_dependency_without_legacy_status(self):
        self.legacy_dependencies(with_status=False)
        before = self.snapshot()
        self.migrate("--dry-run")
        self.assertEqual(before, self.snapshot())
        self.migrate()
        self.assertIn("Depends: T1", self.log.read_text())
        self.assertEqual(self.show("T2")["depends_on"], ["T1"])
        value = json.loads((self.root / "lb/log.md.json").read_text())
        self.assertNotIn("depends_on", value["documents"]["log.md"]["task"]["T2"])
        after = self.snapshot()
        self.migrate()
        self.assertEqual(after, self.snapshot())

    def test_replacement_requires_migration_of_legacy_references(self):
        self.legacy_dependencies()
        (self.root / "replace.json").write_text(
            json.dumps(
                {
                    "task_id": "T1",
                    "replacements": [
                        {"id": "T3", "text": "Heading"},
                        {"id": "T4", "text": "Paragraph"},
                    ],
                    "reference_changes": {},
                }
            )
        )
        before = self.snapshot()
        self.cli(
            "task",
            "split",
            "log.md",
            "--input-file",
            "replace.json",
            "--decision",
            "Approved replacement",
            "--expect-version",
            self.token(),
            code=4,
        )
        self.assertEqual(before, self.snapshot())

    def test_conflicting_or_invalid_dependencies_refuse_without_writes(self):
        self.legacy_dependencies()
        self.log.write_text(self.log.read_text() + "    - Depends: T2\n")
        before = self.snapshot()
        self.migrate(code=4)
        self.action("start", "T2", code=4)
        self.assertEqual(before, self.snapshot())
        self.log.write_text(self.log.read_text().replace("    - Depends: T2\n", ""))
        path = self.root / "lb/log.md.json"
        value = json.loads(path.read_text())
        value["documents"]["log.md"]["task"]["T2"]["depends_on"] = "T1"
        path.write_text(json.dumps(value))
        before = self.snapshot()
        self.migrate(code=4)
        self.action("start", "T2", code=4)
        self.assertEqual(before, self.snapshot())

    def test_existing_pair_recovery_preserves_metadata_and_bytes(self):
        # Existing recovery mechanism is a control, not new migration certification.
        doc = parse(self.log, self.root)
        records.put(
            doc,
            "lifecycle",
            {
                "value": "active",
                "basis": "Approved",
                "previous": "unknown",
                "at": "2026-01-01T00:00:00Z",
            },
        )
        original = storage._replace
        calls = []

        def interrupt(path, data, expected):
            calls.append(path)
            if len(calls) == 2:
                raise OSError("simulated second-file interruption")
            original(path, data, expected)

        with patch.object(storage, "_replace", side_effect=interrupt):
            with self.assertRaises(OSError):
                storage.write_bytes(doc, doc.data + b"\nRecovery target\n", False)
        self.assertTrue(journal_for(self.log, self.root).exists())
        self.cli("log", "context", "log.md", code=4)
        preview = self.cli("log", "recover", "log.md", "--dry-run")
        self.cli(
            "log", "recover", "log.md", "--expect-version", preview["version_token"]
        )
        self.assertFalse(journal_for(self.log, self.root).exists())
        self.assertIn("Recovery target", self.log.read_text())

    def test_stale_disposition_is_not_current_cancellation(self):
        self.fixture("stale-disposition.md")
        before = self.snapshot()
        task = self.context()["stages"][0]["tasks"][0]
        self.assertIsNone(task["resolution"])
        self.assertEqual(before, self.snapshot())

    def test_existing_human_cancellation_retains_provenance(self):
        self.fixture("cancelled.md")
        before = self.snapshot()
        task = self.context()["stages"][0]["tasks"][0]
        self.assertEqual(task["resolution"]["as"], "human-cancelled")
        self.assertEqual(task["resolution"]["decision"], "Explicit human decision")
        self.assertEqual(before, self.snapshot())

    def test_archived_identity_is_not_an_orphan_active_task(self):
        self.legacy()
        path = self.root / "lb/log.md.json"
        state = json.loads(path.read_text())
        state["documents"]["log.md"]["task-archive"] = {
            "removed": {
                "id": "removed",
                "previous_text": "Historical work",
                "replacement_ids": ["T1", "T2"],
            }
        }
        path.write_text(json.dumps(state))
        before = self.snapshot()
        current = self.context()
        self.assertEqual(current["task_identity_errors"], [])
        self.assertEqual({t["id"] for t in current["stages"][0]["tasks"]}, {"T1", "T2"})
        self.assertEqual(before, self.snapshot())

    def test_interrupted_migration_recovers_canonical_target(self):
        from click.testing import CliRunner

        from logbook_cli.cli import app

        self.legacy()
        # A state-only migration is a single atomic replace. Include a legacy
        # dependency to exercise a real Markdown + sidecar transaction.
        path = self.root / "lb/log.md.json"
        state = json.loads(path.read_text())
        state["documents"]["log.md"]["task"]["T2"]["depends_on"] = ["T1"]
        path.write_text(json.dumps(state))
        token = self.token()
        original = storage._replace
        count = 0

        def interrupt(path, data, expected):
            nonlocal count
            count += 1
            if count == 2:
                raise OSError("simulated migration interruption")
            original(path, data, expected)

        with patch.object(storage, "_replace", side_effect=interrupt):
            result = CliRunner().invoke(
                app,
                [
                    "--root",
                    str(self.root),
                    "task",
                    "migrate",
                    "log.md",
                    "--expect-version",
                    token,
                    "--json",
                ],
            )
        self.assertEqual(getattr(result.exception, "code", None), 4, result.output)
        self.assertTrue(journal_for(self.log, self.root).exists())
        preview = self.cli("log", "recover", "log.md", "--dry-run")
        self.cli(
            "log", "recover", "log.md", "--expect-version", preview["version_token"]
        )
        self.assertEqual(self.show("T1")["status"], "done")
        self.assertEqual(self.show("T2")["status"], "active")
        self.assertFalse(journal_for(self.log, self.root).exists())
