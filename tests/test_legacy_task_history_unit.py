"""Unit coverage for Task history and disposition migration."""

import hashlib
from pathlib import Path
from unittest import TestCase

from logbook_cli.document import LbError
from logbook_cli.legacy_conversion import document_state

ROOT = Path("/example")
PATH = "docs/sample.md"


def markdown(line, annotation=""):
    return (
        "# Sample\n\n## Stage 01 Build\n\n"
        "- [x] First task\n    <!-- lb-task task-first -->\n"
        + line
        + "\n    <!-- lb-task task-example -->\n"
        + annotation
    ).encode()


class LegacyTaskHistoryTest(TestCase):
    def current(self, line, annotation, record):
        return document_state(
            ROOT,
            ROOT,
            PATH,
            markdown(line, annotation),
            {"task": {"task-first": {"id": "task-first"}, "task-example": record}},
        )["tasks"]["task-example"]

    def test_old_status_and_dependency_history_do_not_override_markdown(self):
        record = {
            "id": "task-example",
            "basis": "Historical owner note",
            "history": [
                {"previous_record": {"status": "accepted", "depends_on": ["old-task"]}}
            ],
        }
        item = self.current("- [ ] Example task", "    - Depends: task-first\n", record)
        self.assertEqual(item["effective_state"], "pending")
        self.assertEqual(item["dependencies"], ["task-first"])
        self.assertNotIn("basis", item)
        self.assertNotIn("history", item)
        for values, message in (
            ({"status": "active"}, "facts without a Markdown equivalent"),
            ({"depends_on": ["old-task"]}, "conflicting legacy dependencies"),
        ):
            with self.subTest(values=values), self.assertRaisesRegex(LbError, message):
                self.current(
                    "- [ ] Example task", "    - Depends: task-first\n", record | values
                )

    def test_checked_receipt_is_equivalent_to_readable_markdown(self):
        resolution = {
            "task": hashlib.sha256(b"Example task").hexdigest(),
            "as": "cancelled",
            "decision": "reviewed <decision>",
            "note": "reason",
            "actor": "example-owner",
            "source": "historical evidence",
        }
        annotation = "    - Resolution: cancelled: reviewed &lt;decision&gt; — reason\n"
        row = {"id": "task-example", "resolution": resolution}
        item = self.current("- [-] Example task", annotation, row)
        self.assertEqual(item["effective_state"], "cancelled")
        self.assertNotIn("resolution", item)
        for readable, record, message in (
            ("", row, "legacy Resolution is missing from Markdown"),
            (annotation, {"id": "task-example"}, "legacy Resolution record is missing"),
            (
                annotation.replace("reason", "different"),
                row,
                "legacy Resolution differs",
            ),
            (
                annotation,
                row | {"resolution": resolution | {"task": "0" * 64}},
                "stale legacy Resolution",
            ),
            (annotation + annotation, row, "legacy Resolution differs"),
        ):
            with (
                self.subTest(message=message),
                self.assertRaisesRegex(LbError, message),
            ):
                self.current("- [-] Example task", readable, record)

    def test_equal_rendering_with_different_decision_and_note_is_ambiguous(self):
        row = {
            "id": "task-example",
            "resolution": {
                "task": hashlib.sha256(b"Example task").hexdigest(),
                "as": "not-applicable",
                "decision": "approved — recorded",
                "note": "reason",
            },
        }
        with self.assertRaisesRegex(LbError, "legacy Resolution differs"):
            self.current(
                "- [-] Example task",
                "    - Resolution: not-applicable: approved — recorded — reason\n",
                row,
            )
