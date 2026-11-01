"""Runner safety checks; these never invoke a live Herdr server."""

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "live_herdr_runner", Path(__file__).parent / "e2e/herdr/run.py"
)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class LiveHerdrRunnerTest(unittest.TestCase):
    def test_snapshot_launcher_retains_virtual_environment_interpreter(self):
        with tempfile.TemporaryDirectory() as temporary:
            suite = runner.LiveSuite({}, Path(temporary))
            self.assertEqual(suite.lb[0], sys.executable)
            result = suite.command([*suite.lb, "--version"])
            self.assertIn("dev", result)

    def test_invalid_configuration_does_not_reach_live_setup(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.json"
            for value in (
                [],
                {},
                {"runtimes": {"codex": {"kind": "codex", "args": "--flag"}}},
                {"runtimes": {"codex": {"kind": "codex"}}, "turn_timeout": 0},
            ):
                with self.subTest(value=value):
                    path.write_text(json.dumps(value))
                    with self.assertRaises(ValueError):
                        runner.load_config(path)

    def test_non_managed_caller_is_rejected_before_any_command(self):
        with patch.object(
            sys, "argv", ["run.py", "--run-live", "--config", "x", "--output", "y"]
        ):
            with patch.dict("os.environ", {"HERDR_ENV": "0"}):
                with patch.object(runner.subprocess, "run") as execute:
                    with self.assertRaises(SystemExit) as result:
                        runner.main()
                    self.assertEqual(result.exception.code, 2)
                    execute.assert_not_called()

    def test_changed_identity_cleanup_does_not_fall_back_to_pane_close(self):
        with tempfile.TemporaryDirectory() as temporary:
            suite = runner.LiveSuite({}, Path(temporary))
            suite.owned = ["w1:p2"]
            suite.bindings = {"codex": {"pane_id": "w1:p2"}}
            calls = []

            def herdr(*args, **kwargs):
                calls.append(args)
                return {
                    "result": {"panes": [{"pane_id": "w1:p1"}, {"pane_id": "w1:p2"}]}
                }

            suite.herdr = herdr
            with patch.object(
                suite, "command", side_effect=AssertionError("identity changed")
            ):
                with patch.dict("os.environ", {"HERDR_WORKSPACE_ID": "w1"}):
                    with self.assertRaises(AssertionError):
                        suite.close()
            self.assertFalse(any(c[:2] == ("pane", "close") for c in calls))
            cleanup = json.loads((Path(temporary) / "cleanup.json").read_text())
            self.assertEqual(cleanup["remaining"], ["w1:p2"])

    def test_busy_read_retains_visible_permission_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            suite = runner.LiveSuite({}, Path(temporary))
            with patch.object(
                suite,
                "herdr",
                side_effect=[
                    AssertionError("agent_not_idle"),
                    "This command requires approval",
                ],
            ) as read:
                self.assertIn("requires approval", suite.read("w1:p2"))
                self.assertEqual(read.call_args.args[-1], "visible")
                self.assertIn(
                    "requires approval",
                    (Path(temporary) / "reply-w1-p2.txt").read_text(),
                )

    def test_identity_unavailable_before_first_turn_does_not_abort_startup(self):
        from logbook_cli.document import LbError

        with tempfile.TemporaryDirectory() as temporary:
            suite = runner.LiveSuite({}, Path(temporary))
            with patch.object(suite, "binding", side_effect=LbError("not ready", 1)):
                self.assertFalse(suite.remember_identity("codex", "w1:p2"))
            self.assertEqual(suite.cleanup_bindings, {})

    def test_unavailable_host_is_blocked_without_turning_continuation_into_failure(
        self,
    ):
        with tempfile.TemporaryDirectory() as temporary:
            suite = runner.LiveSuite({}, Path(temporary))
            passed = suite.record(
                "captain-readiness",
                lambda: suite.captain_readiness(
                    {"reason": "unavailable"}, {"stderr": "Operation not permitted"}
                ),
            )
            self.assertFalse(passed)
            self.assertEqual(suite.checks[0]["status"], "BLOCKED")
            self.assertIn("Operation not permitted", suite.checks[0]["detail"])


if __name__ == "__main__":
    unittest.main()
