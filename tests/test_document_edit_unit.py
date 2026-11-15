import unittest
from pathlib import Path
from unittest.mock import patch

from logbook_cli.repository import edit_document, markdown_document


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
