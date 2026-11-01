"""Validate eval registration and fixture links; never grade Agent behavior."""

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ("lb-plan", "lb-preflight", "lb-update", "lb-push", "lb-status")


class CoordinationEvalRegistryTest(unittest.TestCase):
    def test_registered_cases_have_assertions_and_materializable_inputs(self):
        count = 0
        for skill in SKILLS:
            directory = ROOT / "skills" / skill / "evals"
            cases = json.loads((directory / "evals.json").read_text())["evals"]
            ids = [c["id"] for c in cases]
            self.assertEqual(len(ids), len(set(ids)), skill)
            for case in cases:
                if "coordination_seeds" not in case:
                    continue
                count += 1
                with self.subTest(skill=skill, case=case["id"]):
                    self.assertTrue(case["prompt"].strip())
                    assertions = case["assertions"]
                    names = [a["name"] for a in assertions]
                    self.assertEqual(len(names), len(set(names)))
                    self.assertTrue(names)
                    for a in assertions:
                        self.assertRegex(a["name"], r"^[a-z][a-z0-9_]*$")
                        self.assertIn(a["type"], {"contains", "not_contains"})
                        self.assertTrue(a["check"].strip())
                    self.assertTrue(case["files"])
                    for filename in case["files"]:
                        path = (directory / filename).resolve()
                        self.assertTrue(path.is_relative_to(ROOT / "skills"))
                        fixture = json.loads(path.read_text())
                        files = fixture.get("files", fixture.get("files_override"))
                        self.assertIsInstance(files, dict)
                        for name, content in files.items():
                            self.assertFalse(Path(name).is_absolute())
                            self.assertNotIn("..", Path(name).parts)
                            self.assertIsInstance(content, str)
                            self.assertFalse(re.search(r"(^|/)(evals|grading)(/|\.)", name))
        self.assertGreater(count, 0)

    def test_eval_evidence_resolves_to_registered_case_ids(self):
        rows = json.loads(
            (ROOT / "tests/fixtures/coordination_coverage.json").read_text()
        )["cases"]
        for row in rows:
            evidence = row["evidence"].get("skill-eval")
            if not evidence or evidence["status"] != "authored":
                continue
            with self.subTest(seed=row["id"]):
                self.assertTrue(evidence["artifact_refs"])
                for ref in evidence["artifact_refs"]:
                    path, identity = ref.split("::")
                    cases = json.loads((ROOT / path).read_text())["evals"]
                    case = next(c for c in cases if c["id"] == int(identity))
                    self.assertIn(row["id"], case["coordination_seeds"])
