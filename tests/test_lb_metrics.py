"""Scoped metrics, replay/correction rules and read-only file boundaries."""

import json
import runpy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "skills/lb-push/scripts/run-metrics.py"
MODULE = runpy.run_path(str(SCRIPT))


def event(identity, kind, at="2026-10-14T00:00:00+00:00", **fields):
    return dict(run_id="run-a", event_id=identity, type=kind, scope="logbook", at=at, origin="host", **fields)


class MetricsTest(unittest.TestCase):
    def measure(self, events, scope="logbook"):
        text = "```lb-run-events\n" + "\n".join(json.dumps(e) for e in events) + "\n```\n"
        return MODULE["calculate"](MODULE["events"](text), "run-a", scope)

    def boundaries(self):
        return [event("start", "run_start", coverage="complete"), event("end", "run_end", at="2026-10-14T00:10:00+00:00", coverage="complete")]

    def test_unknown_and_zero_denominator_do_not_fabricate_success(self):
        result = self.measure([])
        self.assertIsNone(result["wall_seconds"])
        self.assertIsNone(result["human_interactions"]["total"])
        self.assertIsNone(result["first_pass"]["rate"])
        result = self.measure(self.boundaries())
        self.assertEqual(result["wall_seconds"], 600)
        self.assertEqual(result["first_pass"]["denominator"], 0)
        self.assertIsNone(result["first_pass"]["rate"])

    def test_overlapping_wait_interruptions_and_turn_dedup(self):
        data = self.boundaries() + [event("wait1", "wait_start", at="2026-10-14T00:01:00+00:00", interval_id="w"), event("wait2", "wait_end", at="2026-10-14T00:04:00+00:00", interval_id="w"), event("out1", "interruption_start", at="2026-10-14T00:03:00+00:00", interval_id="i"), event("out2", "interruption_end", at="2026-10-14T00:05:00+00:00", interval_id="i"), event("turn1", "human_turn", human_turn_id="h", category="gate"), event("turn2", "human_turn", human_turn_id="h", category="additional"), event("resume", "run_resume")]
        result = self.measure(data + [data[-1]])
        self.assertEqual(result["wait_seconds"], 180)
        self.assertEqual(result["interruption_seconds"], 120)
        self.assertEqual(result["unavailable_union_seconds"], 240)
        self.assertEqual(result["remaining_wall_seconds"], 360)
        self.assertEqual(result["human_interactions"]["total"], 1)
        self.assertEqual(result["human_interactions"]["known_categories"]["gate"], 1)

    def test_correction_preserves_failed_first_pass_after_rework(self):
        data = self.boundaries() + [event("first", "package_first_outcome", package_id="p", outcome="passed", first_pass=True), event("defect", "package_correction", package_id="p", corrects="first", outcome="failed", first_pass=False, reason="delivery defect"), event("fixed", "package_correction", package_id="p", corrects="defect", outcome="passed", first_pass=True, reason="rework passed")]
        result = self.measure(data)
        self.assertEqual(result["first_pass"], {"numerator": 0, "denominator": 1, "rate": 0.0})
        data[-1]["corrects"] = "fixed"
        with self.assertRaises(ValueError):
            self.measure(data)

    def test_partial_open_wait_and_stage_clipping(self):
        data = self.boundaries() + [event("open", "wait_start", interval_id="w")]
        result = self.measure(data)
        self.assertIsNone(result["wait_seconds"])
        self.assertIsNone(result["remaining_wall_seconds"])
        partial = self.boundaries()
        partial[0]["coverage"] = "partial"
        self.assertIsNone(self.measure(partial)["first_pass"]["rate"])
        data = [dict(event("s", "scope_start", coverage="complete"), scope="Stage 01"), dict(event("e", "scope_end", at="2026-10-14T00:02:00+00:00", coverage="complete"), scope="Stage 01"), dict(event("w1", "wait_start", at="2026-10-13T23:59:00+00:00", interval_id="w"), scope="Stage 01"), dict(event("w2", "wait_end", at="2026-10-14T00:03:00+00:00", interval_id="w"), scope="Stage 01")]
        self.assertEqual(self.measure(data, "Stage 01")["wait_seconds"], 120)

    def test_conflicting_replay_unknown_time_and_duplicate_initial_outcome(self):
        with self.assertRaises(ValueError):
            self.measure([event("a", "run_resume"), event("a", "run_end")])
        with self.assertRaises(ValueError):
            self.measure([event("a", "run_start", at="2026-10-14T00:00:00")])
        data = self.boundaries() + [event("first", "package_first_outcome", package_id="p", outcome="unknown", first_pass=None), event("second", "package_first_outcome", package_id="p", outcome="passed", first_pass=True)]
        with self.assertRaises(ValueError):
            self.measure(data)
        data = self.boundaries()
        data[0]["at"] = None
        self.assertIsNone(self.measure(data)["wall_seconds"])

    def test_hidden_example_events_do_not_create_metrics(self):
        example = "<!-- example only\n```lb-run-events\n" + "\n".join(json.dumps(e) for e in self.boundaries()) + "\n```\n-->"
        self.assertEqual(MODULE["events"](example), [])
        live = "\n```lb-run-events\n" + json.dumps(event("live", "run_resume")) + "\n```"
        self.assertEqual(len(MODULE["events"](example + live)), 1)

    def test_unknown_first_pass_is_not_a_fabricated_zero_and_numeric_flags_refuse(self):
        data = self.boundaries() + [event("p", "package_first_outcome", package_id="p", outcome="passed", first_pass=None)]
        result = self.measure(data)
        self.assertIsNone(result["first_pass"]["rate"])
        self.assertIsNone(result["first_pass"]["numerator"])
        self.assertEqual(result["first_pass"]["known_numerator"], 0)
        data[-1]["first_pass"] = 1
        with self.assertRaises(ValueError):
            self.measure(data)

    def test_helper_reads_only_existing_thinking_and_refuses_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "thinking.md"
            path.write_text("no event history\n")
            before = path.read_bytes()
            result = subprocess.run([sys.executable, str(SCRIPT), "--root", directory, "--thinking", "thinking.md", "--run-id", "run-a"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["coverage"], "unknown")
            self.assertEqual(path.read_bytes(), before)
            result = subprocess.run([sys.executable, str(SCRIPT), "--root", directory, "--thinking", "../missing.md", "--run-id", "run-a"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 3)
            self.assertEqual(list(root.iterdir()), [path])
