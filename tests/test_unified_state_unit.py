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
