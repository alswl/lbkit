"""Unit regressions for retained observations and offline check diagnostics."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from logbook_cli.document import (
    LbError,
    check,
    context,
    links_for,
    parse_text,
    stage_state,
)
from logbook_cli.edit import require_valid_candidate
from logbook_cli.link_records import digest, local_digest, occurrence, task_binding
from logbook_cli.repository import markdown_document
from logbook_cli.services import tasks
from logbook_cli.services.closeout import audit_links
from logbook_cli.services.logbook import validate
from logbook_cli.usage import work_dirs
from logbook_cli.views import state_snapshot


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        self.path = self.root / "delivery.md"

    def document(self, body):
        return parse_text(("# Delivery\n" + body).encode(), self.path, self.root)

    def test_placeholder_and_scope_limits_are_not_check_failures(self):
        doc = self.document(
            "## 🛫 Stage 01 Release\n"
            "阶段占位：待人工授权\n"
            "[Remote](https://example.org/release)\n"
            "[Other workspace](../elsewhere.md)\n"
        )
        with (
            patch("logbook_cli.services.logbook.safe_path", return_value=self.path),
            patch("logbook_cli.services.logbook.parse", return_value=doc),
        ):
            result = validate(str(self.root), self.path.name, False, "projects")
        self.assertEqual(result.code, 0)
        self.assertEqual(
            {row["code"]: (row["category"], row["severity"]) for row in result.value},
            {
                "STAGE_PLACEHOLDER": ("stage_placeholder", "notice"),
                "LINK_UNVERIFIED": ("verification_limit", "notice"),
                "LOCAL_LINK_UNVERIFIED": ("verification_limit", "notice"),
            },
        )
        self.assertIsNone(stage_state(doc.stages[0]))
        self.assertIsNone(context(doc)["next_task"])

    def test_structural_errors_and_missing_links_still_fail(self):
        doc = self.document(
            "## Stage 01 Empty\n"
            "## Stage 02 Broken\n"
            "Stage placeholder: Waiting for approval\n"
            "- [?] Invalid task\n"
            "[Gone](gone%20file.md)\n"
        )
        with (
            patch("logbook_cli.services.logbook.safe_path", return_value=self.path),
            patch("logbook_cli.services.logbook.parse", return_value=doc),
        ):
            result = validate(str(self.root), self.path.name, False, "projects")
        self.assertEqual(result.code, 1)
        by_code = {row["code"]: row for row in result.value}
        for code, category in (
            ("EMPTY_STAGE", "structural_error"),
            ("INVALID_STAGE_PLACEHOLDER", "structural_error"),
            ("UNKNOWN_TASK_STATE", "structural_error"),
            ("LOCAL_LINK_MISSING", "broken_link"),
        ):
            self.assertIn(code, by_code)
            self.assertEqual(by_code[code].get("category"), category)

    def test_retained_observations_explain_changes_without_verifying_links(self):
        original = self.document(
            "## 🛫 Stage 01 Old\n"
            "- [ ] Deliver\n"
            "    - Artifact: [File](result.md)\n"
            "[Background](https://example.org/reference)\n"
        )
        updated = self.document(
            original.text.removeprefix("# Delivery\n").replace("Old", "New", 1)
        )
        rows = {}
        for link in links_for(original):
            location = occurrence(original, link)
            bound = location["task"]
            row = {
                **{key: link[key] for key in ("label", "target")},
                "anchor": location["anchor"],
                "bound_task": bound,
                "binding": task_binding(original, bound["stage"], bound["text"])
                if bound
                else None,
                "observed_at": "2026-01-01T00:00:00Z",
                "observer": "reviewer",
                "basis": "Earlier observation",
                "outcome": "verified",
                "result_identity": None,
            }
            row["record_id"] = digest(row)
            rows[row["record_id"]] = row
        updated.legacy_metadata = {"link-verification": rows}
        history = context(updated)["link_verifications"]
        self.assertEqual(len(history), 2)
        self.assertTrue(all(not row["applicable"] for row in history))
        self.assertEqual(
            {row["invalidation_reason"] for row in history}, {"link context changed"}
        )
        self.assertEqual(history[0]["bound_task"]["stage"], "Stage 01 Old")
        self.assertEqual(history[0]["target_status"], "missing")
        self.assertEqual(audit_links(updated)["link_verifications"], history)
        self.assertFalse(audit_links(updated)["delivery_ready"])
        self.assertIn("LINK_UNVERIFIED", {row["code"] for row in check(updated)})
        original.legacy_history = {"link-verification": rows}
        current = context(original)["link_verifications"]
        self.assertEqual(len(current), 2)
        self.assertEqual(current[1]["line"], links_for(original)[1]["line"])
        self.assertFalse(current[1]["applicable"])
        self.assertEqual(current[1]["source"], "legacy_history")
        self.assertEqual(
            current[1]["invalidation_reason"],
            "retained legacy observation is historical evidence only",
        )
        original.metadata["link-verification"] = rows
        self.assertNotIn("LINK_UNVERIFIED", {row["code"] for row in check(original)})
        self.assertFalse(audit_links(original)["delivery_ready"])

        no_links = self.document("## Stage 01 New\n- [ ] Deliver\n")
        self.assertEqual(audit_links(no_links)["link_verifications"], [])
        no_links.legacy_metadata = updated.legacy_metadata
        audit = audit_links(no_links)
        self.assertEqual(audit["links"], [])
        self.assertEqual(len(audit["link_verifications"]), 2)
        self.assertEqual(
            {row["invalidation_reason"] for row in audit["link_verifications"]},
            {"recorded link target or label no longer present"},
        )

    def test_structure_only_skips_applicable_local_link_digest(self):
        (self.root / "design.md").write_text("A local deliverable")
        doc = self.document(
            "## 🛫 Stage 01 Delivery\n"
            "- [ ] Deliver\n"
            "[Design](design.md)\n"
            "[Gone](missing.md)\n"
        )
        link = links_for(doc)[0]
        row = {
            "label": link["label"],
            "target": link["target"],
            "anchor": occurrence(doc, link)["anchor"],
            "binding": None,
            "bound_task": None,
            "observed_at": "2026-01-01T00:00:00Z",
            "observer": "reviewer",
            "basis": "Earlier observation",
            "outcome": "verified",
            "result_identity": None,
            "local_digest": local_digest(doc, link["target"]),
        }
        row["record_id"] = digest(row)
        records = {"link-verification": {row["record_id"]: row}}
        doc.metadata = records

        with patch("logbook_cli.link_records.local_digest", wraps=local_digest) as probe:
            self.assertTrue(context(doc)["link_verifications"][0]["applicable"])
            self.assertEqual({item["code"] for item in check(doc)}, {"LOCAL_LINK_MISSING"})
            self.assertTrue(audit_links(doc)["link_verifications"][0]["applicable"])
            self.assertEqual(probe.call_count, 3)
            probe.reset_mock()

            view = context(doc, no_link_content=True)
            self.assertEqual(view["next_task"]["text"], "Deliver")
            self.assertEqual(state_snapshot(doc)["next_task"], view["next_task"])
            self.assertEqual(view["related_links"], links_for(doc))
            observation = view["link_verifications"][0]
            self.assertFalse(observation["applicable"])
            self.assertEqual(observation["target_status"], "ok")
            self.assertIn("bytes not checked", observation["invalidation_reason"])
            findings = {item["code"]: item for item in check(doc, no_link_content=True)}
            self.assertEqual(findings["LOCAL_LINK_CONTENT_UNCHECKED"]["severity"], "notice")
            self.assertEqual(findings["LOCAL_LINK_MISSING"]["severity"], "error")
            probe.assert_not_called()

            candidate = doc.text + "- [ ] Another delivery\n"
            require_valid_candidate(doc, candidate)
            previous = parse_text(
                doc.text.replace("[Design](design.md)\n", "").encode(),
                doc.path,
                doc.root,
                source=doc,
            )
            require_valid_candidate(previous, doc.text)
            with self.assertRaisesRegex(LbError, "LOCAL_LINK_MISSING"):
                require_valid_candidate(doc, candidate + "[Missing](another.md)\n")

            with patch.object(tasks, "load", return_value=doc):
                self.assertEqual(
                    tasks.next_task(str(self.root), self.path.name).value,
                    view["next_task"],
                )
            with (
                patch("logbook_cli.usage.discover", return_value=[self.path]),
                patch("logbook_cli.usage.parse", return_value=doc),
            ):
                self.assertEqual(work_dirs(self.root, "projects"), [self.root])
            probe.assert_not_called()

            current = markdown_document(doc.data, doc.path, doc.root)
            current.legacy_metadata = records
            for no_link_content in (False, True):
                history = context(current, no_link_content=no_link_content)[
                    "link_verifications"
                ][0]
                self.assertFalse(history["applicable"])
                self.assertIn("historical evidence only", history["invalidation_reason"])
                findings = check(current, no_link_content=no_link_content)
                self.assertIn("LOCAL_LINK_MISSING", {item["code"] for item in findings})
            probe.assert_not_called()

    def test_hidden_empty_and_duplicate_declarations_do_not_waive_empty_stage(self):
        for declaration, invalid in (
            ("<!-- Stage placeholder: Hidden -->\n", False),
            ("```md\nStage placeholder: Example\n```\n", False),
            ("Stage placeholder:   \n", True),
            ("Stage placeholder: First\nStage placeholder: Second\n", True),
        ):
            with self.subTest(declaration=declaration):
                doc = self.document("## Stage 01 Empty\n" + declaration)
                codes = {row["code"] for row in check(doc)}
                self.assertIn("EMPTY_STAGE", codes)
                self.assertNotIn("STAGE_PLACEHOLDER", codes)
                self.assertEqual("INVALID_STAGE_PLACEHOLDER" in codes, invalid)

    def test_local_target_status_respects_symlinks_and_encoded_paths(self):
        from logbook_cli.document import resolve_link_target

        outside = self.root.parent / "unapproved.md"
        (self.root / "escape.md").symlink_to(outside)
        (self.root / "dangling.md").symlink_to("absent.md")
        existing = self.root / "report draft.md"
        existing.touch()
        lstat = Path.lstat

        def inspect(path):
            self.assertTrue(path.is_relative_to(self.root), path)
            return lstat(path)

        with patch.object(Path, "lstat", inspect):
            for target, expected in (
                ("escape.md", "outside"),
                ("dangling.md", "missing"),
                ("report%20draft.md#section", "ok"),
                (existing.as_uri(), "ok"),
                ("file://other.example.org/share/report.md", "outside"),
            ):
                with self.subTest(target=target):
                    self.assertEqual(
                        resolve_link_target(self.root, self.path, target)[0], expected
                    )
