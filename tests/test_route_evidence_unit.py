import unittest

from logbook_cli.document import LbError
from logbook_cli.services.route_evidence import parse_evidence, replace_evidence


class RouteEvidenceTests(unittest.TestCase):
    def test_missing_section_is_empty(self):
        self.assertIsNone(parse_evidence("# Thinking\n\nNotes\n"))

    def test_round_trip_preserves_surrounding_content(self):
        text = "# Thinking\n\nKeep me.\n\n## Other\n\nHuman note.\n"
        evidence = {
            "run_ref": "sample",
            "confirmations": [],
            "observations": [],
            "grants": [],
        }
        changed = replace_evidence(text, evidence)
        self.assertEqual(parse_evidence(changed), evidence)
        self.assertIn("Keep me.\n\n## Other\n\nHuman note.", changed)
        self.assertEqual(replace_evidence(changed, evidence), changed)

    def test_duplicate_and_invalid_sections_are_rejected(self):
        section = "## 路线确认与预检\n\n```json\n{}\n```\n"
        with self.assertRaises(LbError):
            parse_evidence(section + section)
        with self.assertRaises(LbError):
            parse_evidence(section)

    def test_preserves_crlf(self):
        value = {"run_ref": "x", "confirmations": [], "observations": [], "grants": []}
        changed = replace_evidence("# Thinking\r\n", value)
        self.assertNotIn("\n", changed.replace("\r\n", ""))
        self.assertEqual(parse_evidence(changed), value)

    def test_update_retains_historical_records_and_checks_run(self):
        from logbook_cli.services.route_evidence import merge_evidence

        base = {
            "run_ref": "run",
            "confirmations": [{"source": "first"}],
            "observations": [],
            "grants": [],
        }
        self.assertEqual(merge_evidence(base, base, "run"), base)
        with self.assertRaises(LbError):
            merge_evidence(base, {**base, "confirmations": []}, "run")
        with self.assertRaises(LbError):
            merge_evidence(None, base, "different")

    def test_explicit_replacement_must_target_same_scope(self):
        from logbook_cli.services.route_evidence import active_records

        original = {"id": "old", "task_id": "A", "object": "snapshot"}
        replacement = {**original, "id": "new", "supersedes": "old"}
        self.assertEqual(
            active_records("observations", [original, replacement]), [replacement]
        )
        with self.assertRaises(LbError):
            active_records("observations", [original, {**replacement, "task_id": "B"}])
        with self.assertRaises(LbError):
            active_records("observations", [original, {**original, "object": "other"}])

    def test_binding_rejects_logbook_and_other_run_document(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from types import SimpleNamespace

        from logbook_cli.services.route_evidence import bound_thinking

        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            for name in ("log.md", "thinking.md", "other.md"):
                (root / name).touch()
            doc = SimpleNamespace(root=root, path=root / "log.md")
            identity = {"document_paths": ["log.md", "thinking.md"]}
            self.assertEqual(
                bound_thinking(doc, identity, "thinking.md"), root / "thinking.md"
            )
            for name in ("log.md", "other.md"):
                with self.assertRaises(LbError):
                    bound_thinking(doc, identity, name)

    def test_quoted_heading_inside_fence_is_ordinary_prose(self):
        text = "# Thinking\n\n```markdown\n## 路线确认与预检\n```\n"
        self.assertIsNone(parse_evidence(text))
