"""Historical migration checks for identity and evidence scope."""

import unittest
from pathlib import Path

from logbook_cli import legacy_conversion, link_records
from logbook_cli.document import LbError, parse_text


class LegacyHistoryTest(unittest.TestCase):
    def test_link_binding_pairs_cannot_disagree_even_with_valid_record_digest(self):
        root = Path("/example")
        doc = parse_text(b"# Sample\n", root / "sample.md", root)
        row = {
            "target": "https://example.com/old",
            "label": "Example",
            "anchor": "a" * 64,
            "binding": None,
            "bound_task": {"stage": "Stage 01 Build", "text": "Historical work"},
            "observed_at": "2025-01-01T00:00:00Z",
            "observer": "example-observer",
            "basis": "example inspection",
            "outcome": "verified",
            "result_identity": "old-version",
        }
        row["record_id"] = link_records.digest(row)
        rows = {row["record_id"]: row}
        doc.metadata["link-verification"] = rows
        with self.assertRaisesRegex(
            LbError, "ambiguous legacy link verification binding"
        ):
            legacy_conversion.verification_history(doc, rows)

    def test_original_archive_id_cannot_disagree_with_its_inline_anchor(self):
        root = Path("/example")
        row = {
            "id": "task-original",
            "basis": "reviewed split",
            "previous_text": "Original work",
            "content": "- [/] Original work\n    <!-- lb-task task-other -->\n",
            "replacement_ids": ["task-one", "task-two"],
        }
        doc = parse_text(b"# Sample\n", root / "sample.md", root)
        with self.assertRaisesRegex(LbError, "original does not match its identity"):
            legacy_conversion.archive_history(doc, {row["id"]: row})

    def test_replacement_can_be_archived_again_but_must_have_one_owner(self):
        document = "docs/sample.md"
        projections = {document: {"tasks": {"task-one": {}, "task-two": {}}}}
        rows = {
            "old-one": {"replacement_ids": ["old-two", "task-one"]},
            "old-two": {"replacement_ids": ["task-one", "task-two"]},
        }
        history = {document: {"task-archive": rows}}
        legacy_conversion.validate_archive_references(projections, history)
        projections["docs/another.md"] = {"tasks": {"task-two": {}}}
        with self.assertRaisesRegex(LbError, "unverified replacement: task-two"):
            legacy_conversion.validate_archive_references(projections, history)
        projections.pop("docs/another.md")
        rows["old-two"]["replacement_ids"][0] = "old-one"
        with self.assertRaisesRegex(LbError, "archive replacement cycle"):
            legacy_conversion.validate_archive_references(projections, history)
