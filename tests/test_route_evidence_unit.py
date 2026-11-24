import unittest

from logbook_cli.document import EXIT_REFUSED, LbError
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

    def test_new_readiness_sources_must_be_nonempty_strings(self):
        from logbook_cli.services.route_evidence import merge_evidence

        base = {
            "run_ref": "run",
            "confirmations": [],
            "observations": [],
            "grants": [],
        }
        for kind in ("confirmations", "observations", "grants"):
            valid = {**base, kind: [{"source": "verified fixture source"}]}
            self.assertEqual(merge_evidence(None, valid, "run"), valid)
            for record in (
                {"source": {"kind": "human_instruction", "ref": "fixture source"}},
                {"source": " \t "},
                {},
            ):
                with self.subTest(kind=kind, record=record):
                    proposed = {**base, kind: [record]}
                    with self.assertRaisesRegex(LbError, "source") as refused:
                        merge_evidence(None, proposed, "run")
                    self.assertEqual(refused.exception.code, EXIT_REFUSED)

    def test_bad_new_source_never_reaches_thinking_editor(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from types import SimpleNamespace
        from unittest.mock import patch

        from logbook_cli.services.route_evidence import update_evidence

        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            thinking = root / "thinking.md"
            original = b"# Thinking\n\nKeep this note.\n"
            thinking.write_bytes(original)
            doc = SimpleNamespace(root=root, path=root / "log.md")
            run = {"identity": {"run_id": "run", "document_paths": ["thinking.md"]}}
            proposed = {
                "run_ref": "run",
                "confirmations": [
                    {"source": {"kind": "human_instruction", "ref": "fixture"}}
                ],
                "observations": [],
                "grants": [],
            }
            with (
                patch("logbook_cli.unified.locate", return_value=(None, run)),
                patch("logbook_cli.repository.sync_status", return_value="synced"),
                patch("logbook_cli.repository.edit_document") as edit,
            ):
                for dry_run in (True, False):
                    with self.subTest(dry_run=dry_run):
                        with self.assertRaisesRegex(LbError, "source"):
                            update_evidence(
                                doc, "thinking.md", proposed, dry_run=dry_run
                            )
                        self.assertEqual(thinking.read_bytes(), original)
                edit.assert_not_called()

    def test_legacy_invalid_source_remains_readable_as_history(self):
        from logbook_cli.services.route_evidence import merge_evidence

        old = {
            "run_ref": "run",
            "confirmations": [{"id": "older", "source": {"ref": "old evidence"}}],
            "observations": [],
            "grants": [],
        }
        stored = replace_evidence("# Thinking\n", old)
        self.assertEqual(parse_evidence(stored), old)
        replacement = {
            "id": "new",
            "supersedes": "older",
            "source": "recovered evidence",
        }
        proposed = {**old, "confirmations": [*old["confirmations"], replacement]}
        self.assertEqual(merge_evidence(old, proposed, "run"), proposed)

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

    def test_observation_action_is_optional_and_only_applies_to_task_observations(self):
        value = {
            "run_ref": "run",
            "confirmations": [],
            "observations": [],
            "grants": [],
        }
        task = {"task_id": "A", "status": "ready"}
        for row in (
            task,
            {**task, "action": "dispatch"},
            {**task, "action": "takeover"},
        ):
            history = {**value, "observations": [row]}
            self.assertEqual(
                parse_evidence(replace_evidence("# Thinking\n", history)), history
            )
        for row in (
            {**task, "action": None},
            {**task, "action": "other"},
            {"scope": "route", "action": "dispatch"},
            {**task, "scope": "route", "action": "dispatch"},
        ):
            with self.subTest(row=row), self.assertRaises(LbError):
                replace_evidence("# Thinking\n", {**value, "observations": [row]})

    def test_observations_cannot_replace_records_for_another_action(self):
        from logbook_cli.services.route_evidence import active_records

        original = {
            "id": "old",
            "task_id": "A",
            "object": "snapshot",
            "action": "dispatch",
        }
        replacement = {**original, "id": "new", "supersedes": "old"}
        self.assertEqual(
            active_records("observations", [original, replacement]), [replacement]
        )
        for row in (
            {**replacement, "action": "takeover"},
            {key: value for key, value in replacement.items() if key != "action"},
        ):
            with self.subTest(row=row), self.assertRaises(LbError):
                active_records("observations", [original, row])

    def test_quoted_heading_inside_fence_is_ordinary_prose(self):
        text = "# Thinking\n\n```markdown\n## 路线确认与预检\n```\n"
        self.assertIsNone(parse_evidence(text))
