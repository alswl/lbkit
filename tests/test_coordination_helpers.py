"""Exercise the offline process harness before trusting its red product tests."""

import concurrent.futures
import subprocess

from coordination_helpers import CoordinationTest


class HarnessTest(CoordinationTest):
    def test_real_entry_and_unscripted_runtime_are_isolated(self):
        self.assertIn("version_token", self.context())
        result = self.run_process(["herdr", "agent", "get", "w1:p1"])
        self.assertEqual(result.returncode, 97)
        self.assertIn("Unscripted", result.stderr)
        self.assertEqual([c["kind"] for c in self.calls()], ["start", "exit"])

    def test_scripted_get_wait_start_and_close(self):
        commands = [
            ["agent", "get"],
            ["agent", "wait"],
            ["agent", "start"],
            ["pane", "close"],
        ]
        self.script(
            [
                {"argv": args, "responses": [{"stdout": {"ok": True}}]}
                for args in commands
            ]
        )
        for command in commands:
            result = self.run_process(["herdr", *command, "w1:p1"])
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("true", result.stdout)

    def test_concurrent_calls_consume_distinct_script_positions(self):
        self.script(
            [
                {
                    "argv": ["agent", "get"],
                    "responses": [{"stdout": {"n": n}} for n in range(8)],
                }
            ]
        )
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            results = list(
                executor.map(
                    lambda _: self.run_process(["herdr", "agent", "get", "w1:p1"]),
                    range(8),
                )
            )
        self.assertEqual(len({r.stdout for r in results}), 8)
        self.assertTrue(all(r.returncode == 0 for r in results))

    def test_timeout_cleans_owned_process(self):
        self.script([{"argv": ["agent", "wait"], "responses": [{"delay": 20}]}])
        with self.assertRaises(subprocess.TimeoutExpired):
            self.run_process(["herdr", "agent", "wait", "w1:p1"], timeout=0.3)
        calls = self.calls()
        self.assertTrue(any(c["kind"] == "signal" for c in calls))
        self.assertTrue(any(c["kind"] == "exit" for c in calls))

    def test_scripted_oversize_and_invalid_json_are_not_normalized(self):
        self.script(
            [
                {
                    "argv": ["agent", "get"],
                    "responses": [
                        {"stdout_bytes": 262145},
                        {"stdout": "{invalid", "code": 3},
                    ],
                }
            ]
        )
        first = self.run_process(["herdr", "agent", "get"])
        self.assertEqual(len(first.stdout), 262145)
        second = self.run_process(["herdr", "agent", "get"])
        self.assertEqual((second.returncode, second.stdout), (3, "{invalid"))
