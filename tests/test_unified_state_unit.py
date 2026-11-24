import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from logbook_cli import unified
from logbook_cli.document import LbError


class UnifiedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.log = self.root / "work.md"
        self.log.write_text("# Work\n## Stage 1\n")

    def test_initialize_replay_and_conflicting_identity(self):
        first = unified.initialize(self.root, self.log, "work", [], False)
        self.assertTrue(first["changed"])
        self.assertFalse(
            unified.initialize(self.root, self.log, "work", [], False)["changed"]
        )
        other = self.root / "other.md"
        other.write_text("# Other\n")
        with self.assertRaises(LbError):
            unified.initialize(self.root, other, "work", [], False)

    def test_dry_run_does_not_create_directory(self):
        unified.initialize(self.root, self.log, "work", [], True)
        self.assertFalse((self.root / "lb").exists())

    def test_malformed_and_old_state_refused(self):
        (self.root / "lb").mkdir()
        old = self.root / "lb/work.md.json"
        old.write_text("{}")
        with self.assertRaises(LbError):
            unified.initialize(self.root, self.log, "work", [], False)
        old.unlink()
        (self.root / "lb/work.json").write_text("{")
        with self.assertRaises(LbError):
            unified.initialize(self.root, self.log, "work", [], False)

    def test_publish_failure_keeps_previous_file(self):
        unified.initialize(self.root, self.log, "work", [], False)
        path = self.root / "lb/work.json"
        before = path.read_bytes()
        value = unified.read(path)
        value["documents"]["work.md"] = {"source_digest": "new"}
        with patch(
            "logbook_cli.storage.replace_bytes_at", side_effect=OSError("disk failed")
        ):
            with self.assertRaises(OSError):
                unified.publish(path, value)
        self.assertEqual(before, path.read_bytes())

    def test_sync_replaces_projection_without_discarding_nested_history(self):
        from contextlib import nullcontext
        from copy import deepcopy

        from logbook_cli.repository import sync_document

        prior = {
            "documents": {
                "work.md": {
                    "source_digest": "old",
                    "stages": ["Old"],
                    "tasks": {},
                    "legacy_metadata": {
                        "task": {"old": {"decision": "Earlier decision"}},
                        "task-archive": {"archived": {"id": "archived"}},
                        "link-verification": {"observation": {"outcome": "verified"}},
                    },
                },
                "other.md": {"source_digest": "other"},
            },
            "identity": {"run_id": "sample"},
            "execution": {"facts": [{"kind": "submission"}]},
            "monitoring": {"targets": {"target": {"cursor": 10}}},
        }
        value = deepcopy(prior)
        with (
            patch("logbook_cli.unified.writer", return_value=nullcontext()),
            patch(
                "logbook_cli.unified.locate",
                return_value=(self.root / "lb/work.json", value),
            ),
            patch("logbook_cli.unified.publish") as publish,
        ):
            self.assertTrue(sync_document(self.root, self.log, dry_run=True)["changed"])
            publish.assert_not_called()
            self.assertEqual(value, prior)
            self.assertTrue(sync_document(self.root, self.log)["changed"])
            publish.assert_called_once()
            self.assertFalse(sync_document(self.root, self.log)["changed"])
        self.assertEqual(value["documents"]["work.md"]["stages"], ["Stage 1"])
        value["documents"]["work.md"]["stages"] = ["Old"]
        value["documents"]["work.md"]["source_digest"] = "old"
        self.assertEqual(value, prior)

    def test_read_document_loads_nested_history_for_its_own_path(self):
        from logbook_cli.repository import read_document

        retained = {"task-archive": {"retired": {"id": "retired"}}}
        value = {
            "documents": {
                "work.md": {"legacy_metadata": retained},
                "other.md": {
                    "legacy_metadata": {"task": {"another": {"decision": "Other"}}}
                },
            },
            "identity": {"run_id": "sample"},
        }
        target = self.root / "lb/work.json"
        with patch("logbook_cli.unified.locate", return_value=(target, value)):
            doc = read_document(self.root, self.log)
        self.assertEqual(doc.legacy_metadata, retained)
        self.assertEqual(doc.metadata["task-archive"], retained["task-archive"])
        self.assertEqual(doc.state_path, target)
