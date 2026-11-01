"""Fixture traceability; passing does not certify product or Agent behavior."""

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CoordinationCoverageTest(unittest.TestCase):
    def test_seed_inventory_requirements_and_evidence_layers(self):
        rows = json.loads(
            (ROOT / "tests/fixtures/coordination_coverage.json").read_text()
        )["cases"]
        ids = [r["id"] for r in rows]
        self.assertEqual(len(ids), len(set(ids)))
        requirements = {fr for r in rows for fr in r["requirements"]}
        self.assertEqual(requirements, {f"FR-{i:03}" for i in range(1, 28)})
        self.assertEqual({r["story"] for r in rows}, {f"US{i}" for i in range(1, 7)})
        for filename in (
            "coordination_design_cases.json",
            "herdr_wait_design_cases.json",
        ):
            seeds = json.loads((ROOT / "tests/fixtures" / filename).read_text())[
                "cases"
            ]
            for seed in seeds:
                row = next(r for r in rows if r["id"] == seed["id"])
                self.assertTrue(set(seed["layers"]).issubset(row["evidence"]))
        for row in rows:
            with self.subTest(case=row["id"]):
                for path in [row["source"], *row["fixtures"]]:
                    self.assertTrue((ROOT / path).is_file(), path)
                self.assertTrue(row["evidence"])
                for layer, evidence in row["evidence"].items():
                    self.assertIn(
                        layer,
                        {
                            "cli-unit",
                            "cli-e2e",
                            "skill-eval",
                            "adapter-contract",
                            "integration",
                        },
                    )
                    self.assertIn(evidence["status"], {"planned", "authored"})
                    expected_kind = (
                        "eval"
                        if layer == "skill-eval"
                        else "integration"
                        if layer == "integration"
                        else "code"
                    )
                    self.assertEqual(evidence["kind"], expected_kind)
                    for ref in evidence["artifact_refs"]:
                        self.assertTrue((ROOT / ref.split("::")[0]).is_file(), ref)
                        if expected_kind == "code":
                            self.assertTrue(ref.startswith("tests/"), ref)
                        elif expected_kind == "eval":
                            self.assertTrue(ref.startswith("skills/"), ref)
                            self.assertIn("/evals/", ref)

    def test_fixture_sidecars_are_valid_legacy_shapes(self):
        for name in ("legacy.json", "conflict.json"):
            data = json.loads((ROOT / "tests/fixtures/coordination" / name).read_text())
            self.assertEqual(data["format"], "lb-document-state")
            self.assertEqual(
                set(data["documents"]["log.md"]["task"]), {"T1", "T2", "T3"}
            )
