import unittest
from pathlib import Path

from logbook_cli.document import LbError
from logbook_cli.repository import project_document


class ProjectionTests(unittest.TestCase):
    def test_short_id_and_current_markdown(self):
        result = project_document(
            b"# Work\n\n## Stage 1\n- [/] Task\n    <!-- lb-task task-a -->\n",
            Path("docs/work.md"),
            Path("."),
        )
        self.assertEqual(result["tasks"]["task-a"]["effective_state"], "active")
        self.assertEqual(result["tasks"]["task-a"]["text"], "Task")

    def test_missing_duplicate_or_orphan_id_refused(self):
        for body in [
            "- [ ] Task\n",
            "- [ ] Task\n    <!-- lb-task a -->\n    <!-- lb-task a -->\n",
            "<!-- lb-task a -->\n",
        ]:
            with self.subTest(body=body), self.assertRaises(LbError):
                project_document(
                    ("# Work\n## Stage 1\n" + body).encode(), Path("work.md"), Path(".")
                )

    def test_readable_resolution_and_resume(self):
        body = b"# Work\n## Stage 1\n- [-] Task\n    <!-- lb-task a -->\n    - Resolution: cancelled: decision -- why\n"
        with self.assertRaises(LbError):
            project_document(body, Path("work.md"), Path("."))

    def test_dependency_cycle_refused(self):
        data = b"# Work\n## Stage 1\n- [ ] A\n    <!-- lb-task a -->\n    - Depends: b\n- [ ] B\n    <!-- lb-task b -->\n    - Depends: a\n"
        with self.assertRaises(LbError):
            project_document(data, Path("work.md"), Path("."))

    def test_current_lifecycle_comes_from_readable_status(self):
        from logbook_cli.lifecycle import get
        from logbook_cli.repository import markdown_document

        doc = markdown_document(
            b"# Work\n\n> Status: Active\n\n## Stage 1\n- [ ] Task\n",
            Path("/repo/work.md"),
            Path("/repo"),
        )
        doc = markdown_document(
            doc.text.replace("Status: Active", "Status: \U0001f6a7 Active").encode(),
            doc.path,
            doc.root,
        )
        self.assertEqual(get(doc)["value"], "active")
