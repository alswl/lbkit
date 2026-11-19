import unittest
from pathlib import Path

from logbook_cli.document import parse_text
from logbook_cli.services.preflight_findings import missing_skills


class PreflightFindingsTests(unittest.TestCase):
    def test_only_saved_task_annotations_count_for_coverage(self):
        root = Path("/example")
        doc = parse_text(
            b"# Work\n\n## Stage 1\n\n- [ ] Report\n    - Skills: `/main`\n",
            root / "log.md",
            root,
        )
        task = doc.stages[0].tasks[0]
        self.assertEqual(missing_skills(task, ["main", "companion"]), ["companion"])
        self.assertEqual(missing_skills(task, []), [])

    def test_findings_preserve_unknown_and_responsibility(self):
        from logbook_cli.services.preflight_findings import summarize

        findings = summarize(
            [
                {
                    "object": "authentication",
                    "status": "unverified",
                    "source": "no live probe",
                },
                {
                    "object": "snapshot",
                    "status": "missing",
                    "source": "file check",
                    "owner": "operator",
                    "clear_when": "approved snapshot is readable",
                },
                {
                    "object": "preview",
                    "status": "not_applicable",
                    "reason": "no preview capability",
                },
                {
                    "object": "authorization",
                    "status": "unverified",
                    "human_action": "approve action",
                },
            ]
        )
        self.assertEqual(
            [g["object"] for g in findings],
            ["authentication", "snapshot", "authorization"],
        )
        self.assertIsNone(findings[0].get("owner"))
        self.assertEqual(findings[1]["owner"], "operator")
        self.assertEqual(findings[2]["human_action"], "approve action")
