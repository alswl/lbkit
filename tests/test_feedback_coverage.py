"""Validate feedback traceability, not model behavior or live service acceptance."""

import ast
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FEEDBACK_IDS = {
    "2610141649", "2610141650", "2610141651", "2610141652", "2610141653",
    "2610141654", "20261012-skill-coverage", "20261012-workflow-registry",
    "20261012-repository-assignment", "20261013-shared-todo", "20261014-host-config",
    "20261013-analysis-parallel", "20261013-capability-gaps",
    "issue-12", "issue-13", "issue-14", "issue-15", "issue-16", "issue-17",
    "issue-18", "issue-19", "issue-20",
    "20261022-idempotent-takeover",
    "20261022-takeover-dispatch-boundary",
    "20261022-takeover-advancement-scope",
}


class FeedbackCoverageTest(unittest.TestCase):
    def test_feedback_requirements_resolve_to_checks_or_explicit_gaps(self):
        data = json.loads((ROOT / "tests/fixtures/feedback_coverage.json").read_text())
        inventory = json.loads((ROOT / "tests/fixtures/feedback_requirements.json").read_text())
        requirements = {row["id"]: row for row in inventory["feedback"]}
        self.assertEqual(set(requirements), FEEDBACK_IDS)
        self.assertEqual(len(inventory["feedback"]), len(FEEDBACK_IDS))
        rows = data["feedback"]
        self.assertEqual({row["id"] for row in rows}, FEEDBACK_IDS)
        self.assertEqual(len(rows), len(FEEDBACK_IDS), "duplicate feedback ID")
        for row in rows:
            requirement = requirements[row["id"]]
            self.assertTrue(requirement["title"].strip())
            self.assertTrue(requirement["todos"] or requirement.get("source", "").strip())
            self.assertTrue(all(type(n) is int and 5 <= n <= 22 for n in requirement["todos"]))
            expected = requirement["criteria"]
            self.assertTrue(expected)
            self.assertEqual(len({c["id"] for c in expected}), len(expected))
            self.assertTrue(all(c["acceptance"].strip() for c in expected))
            criteria = row["criteria"]
            self.assertTrue(criteria)
            self.assertEqual({c["id"] for c in criteria}, {c["id"] for c in expected},
                             f"requirement missing from coverage: {row['id']}")
            self.assertEqual(len({c["id"] for c in criteria}), len(criteria))
            for criterion in criteria:
                with self.subTest(feedback=row["id"], criterion=criterion["id"]):
                    checks = criterion["checks"]
                    self.assertTrue(checks or criterion.get("gap", "").strip(),
                                    "requirement silently lost: neither check nor explicit gap")
                    for check in checks:
                        if "skill" in check:
                            self.check_skill_assertion(check)
                        else:
                            self.check_cli_test(check)

    def check_skill_assertion(self, check):
        self.assertEqual(set(check), {"skill", "case", "assertion", "type"})
        self.assertRegex(check["skill"], r"^lb-[a-z-]+$")
        self.assertIs(type(check["case"]), int)
        self.assertIn(check["type"], ("contains", "not_contains"))
        path = ROOT / "skills" / check["skill"] / "evals/evals.json"
        cases = json.loads(path.read_text())["evals"]
        matches = [c for c in cases if c["id"] == check["case"]]
        self.assertEqual(len(matches), 1, f"missing/duplicate case: {check}")
        assertions = matches[0].get("assertions", [])
        matches = [a for a in assertions if a["name"] == check["assertion"]]
        self.assertEqual(len(matches), 1, f"missing/duplicate assertion: {check}")
        self.assertEqual(matches[0]["type"], check["type"], f"polarity drift: {check}")
        self.assertTrue(matches[0]["check"].strip(), f"empty assertion: {check}")

    def check_cli_test(self, check):
        self.assertEqual(set(check), {"test"})
        match = re.fullmatch(r"tests\.(test_\w+)\.(\w+)\.(test_\w+)", check["test"])
        self.assertIsNotNone(match, check)
        module, class_name, method = match.groups()
        tree = ast.parse((ROOT / "tests" / f"{module}.py").read_text())
        classes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name]
        self.assertEqual(len(classes), 1, f"missing/duplicate test class: {check}")
        methods = [n for n in classes[0].body if isinstance(n, ast.FunctionDef) and n.name == method]
        self.assertEqual(len(methods), 1, f"missing/duplicate test method: {check}")
        self.assertFalse(methods[0].decorator_list, f"review skipped/decorated coverage: {check}")


if __name__ == "__main__":
    unittest.main()
