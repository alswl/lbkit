import fcntl
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from logbook_cli import state, unified
from logbook_cli.document import LbError, parse_text
from logbook_cli.repository import edit_document, markdown_document
from logbook_cli.storage import WriterBusy, write_bytes


class EditTests(unittest.TestCase):
    def test_dry_run_never_writes(self):
        doc = markdown_document(
            b"# Work\n## Stage 1\n- [ ] Task\n", Path("/repo/work.md"), Path("/repo")
        )
        with patch("logbook_cli.storage.replace_bytes_at") as write:
            result = edit_document(doc, doc.text.replace("[ ]", "[/]"), True)
        write.assert_not_called()
        self.assertTrue(result["sync_required"])
        self.assertFalse(result["document_saved"])


class LegacyMarkdownWriterTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.project = self.root / "sample"
        self.project.mkdir()
        (self.project / "mind.yaml").write_text("{}\n")
        self.path = self.project / "notes.markdown"
        self.data = b"# Notes\n"
        self.path.write_bytes(self.data)

    def test_project_lock_blocks_writes_from_both_root_spellings(self):
        with state.open_directory(self.project, self.project) as fd:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            for root in (self.project, self.root):
                with self.subTest(root=root):
                    doc = parse_text(self.data, self.path, root)
                    with self.assertRaises(WriterBusy):
                        write_bytes(doc, b"# Updated\n", False)
        self.assertEqual(self.path.read_bytes(), self.data)

    def test_late_associated_document_write_checks_current_authority(self):
        for root in (self.project, self.root):
            with self.subTest(root=root):
                doc = parse_text(self.data, self.path, root)
                with patch.object(
                    unified, "locate", return_value=(self.project / "lb/fresh.json", {})
                ) as locate:
                    with self.assertRaisesRegex(LbError, "document authority changed"):
                        write_bytes(doc, b"# Updated\n", False)
                    locate.assert_called_once_with(root, self.path)
        self.assertEqual(self.path.read_bytes(), self.data)
