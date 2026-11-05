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
    def test_two_workers_can_use_the_same_runtime(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.json"
            value = {
                "runtimes": {
                    "codex-a": {"kind": "codex", "args": []},
                    "codex-b": {"kind": "codex", "args": []},
                }
            }
            path.write_text(json.dumps(value))
            self.assertEqual(runner.load_config(path), value)

    def test_stale_caller_blocks_without_starting_test_agents(self):
        with tempfile.TemporaryDirectory() as temporary:
            suite = runner.LiveSuite({}, Path(temporary))
            with patch.object(
                suite, "herdr", side_effect=AssertionError("pane_not_found")
            ) as call:
                with self.assertRaises(runner.Blocked):
                    suite.caller_context()
            self.assertEqual(call.call_args.args, ("pane", "current", "--current"))
            self.assertEqual(suite.owned, [])

    def test_long_foreground_probe_requires_room_for_same_turn_handling(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.json"
            value = {
                "runtimes": {"codex-a": {"kind": "codex"}},
                "foreground_wait_seconds": 90,
                "turn_timeout": 120,
            }
            path.write_text(json.dumps(value))
            self.assertEqual(runner.load_config(path), value)
            for duration in (True, 0, float("nan"), 110, 601):
                with self.subTest(duration=duration):
                    path.write_text(
                        json.dumps({**value, "foreground_wait_seconds": duration})
                    )
                    with self.assertRaises(ValueError):
                        runner.load_config(path)

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

    def test_dedicated_captain_observes_two_workers_not_itself(self):
        with tempfile.TemporaryDirectory() as temporary:
            suite = runner.LiveSuite(
                {
                    "runtimes": {
                        "worker-a": {"kind": "codex"},
                        "worker-b": {"kind": "codex"},
                    },
                    "captain": {"kind": "claude"},
                },
                Path(temporary),
            )
            suite.bindings = {
                "worker-a": {"pane_id": "w1:p1"},
                "worker-b": {"pane_id": "w1:p2"},
                "captain": {"pane_id": "w1:p3"},
            }
            suite.continuations = {}
            with (
                patch.object(suite, "target", side_effect=lambda axis: {"axis": axis}),
                patch.object(suite, "wait", return_value={"next_input": {}}) as wait,
                patch.object(suite, "captain_return", return_value={}),
            ):
                suite.captain_probe("captain")
            self.assertEqual(
                wait.call_args.args[0], [{"axis": "worker-a"}, {"axis": "worker-b"}]
            )

    def test_captain_setup_uses_decoded_command_results(self):
        with tempfile.TemporaryDirectory() as temporary:
            suite = runner.LiveSuite({}, Path(temporary))
            suite.continuations = {"captain": {"targets": []}}
            suite.bindings = {"captain": {"pane_id": "w1:p3"}}
            with (
                patch.object(
                    suite,
                    "command",
                    return_value={"version_token": "fresh", "reason": "timeout"},
                ),
                patch.object(
                    suite, "herdr", side_effect=runner.Blocked("host boundary")
                ),
            ):
                with self.assertRaisesRegex(runner.Blocked, "host boundary"):
                    suite.captain_return("captain")

    def test_agent_layout_rejects_unknown_value_before_launch(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.json"
            path.write_text(
                json.dumps(
                    {"runtimes": {"worker": {"kind": "claude"}}, "agent_layout": "bad"}
                )
            )
            with self.assertRaisesRegex(ValueError, "agent_layout"):
                runner.load_config(path)

    def test_sibling_layout_refuses_a_split_that_hides_question_footer(self):
        with tempfile.TemporaryDirectory() as temporary:
            suite = runner.LiveSuite({}, Path(temporary))
            layout = {
                "result": {
                    "layout": {
                        "panes": [
                            {"pane_id": "w1:p1", "rect": {"width": 90, "height": 29}}
                        ]
                    },
                    "pane": {"pane_id": "w1:p2"},
                }
            }
            with (
                patch.dict("os.environ", {"HERDR_PANE_ID": "w1:p1"}),
                patch.object(suite, "herdr", return_value=layout) as herdr,
            ):
                with self.assertRaisesRegex(runner.Blocked, "agent_layout"):
                    suite.create_agent_pane()
            self.assertEqual(len(herdr.call_args_list), 1)

    def test_tab_layout_creates_full_size_pane_without_splitting_caller(self):
        with tempfile.TemporaryDirectory() as temporary:
            suite = runner.LiveSuite({"agent_layout": "tabs"}, Path(temporary))
            result = {
                "result": {
                    "root_pane": {"pane_id": "w1:p2"},
                    "pane": {"pane_id": "w1:p2"},
                    "layout": {
                        "panes": [
                            {"pane_id": "w1:p1", "rect": {"width": 180, "height": 58}}
                        ]
                    },
                }
            }
            with (
                patch.dict(
                    "os.environ", {"HERDR_PANE_ID": "w1:p1", "HERDR_WORKSPACE_ID": "w1"}
                ),
                patch.object(suite, "herdr", return_value=result) as herdr,
            ):
                self.assertEqual(suite.create_agent_pane()["pane_id"], "w1:p2")
            self.assertEqual(herdr.call_args.args[:2], ("tab", "create"))
            self.assertEqual(len(herdr.call_args_list), 1)
            self.assertIn("--no-focus", herdr.call_args.args)

    def test_captain_consumes_both_initial_gaps_before_measuring_quiet(self):
        with tempfile.TemporaryDirectory() as temporary:
            suite = runner.LiveSuite({}, Path(temporary))
            suite.continuations = {"captain": {"targets": [{}, {}]}}
            suite.bindings = {"captain": {"pane_id": "w1:p3"}}
            results = iter(
                [
                    {"reason": "change"},
                    {"reason": "change"},
                    {"reason": "timeout"},
                ]
            )
            waits = []

            def command(argv, **kwargs):
                if "wait" in argv:
                    result = next(results)
                    waits.append(result)
                    return result
                return {"version_token": "fresh"}

            with (
                patch.object(suite, "command", side_effect=command),
                patch.object(
                    suite, "herdr", side_effect=runner.Blocked("host boundary")
                ),
            ):
                with self.assertRaisesRegex(runner.Blocked, "host boundary"):
                    suite.captain_return("captain")
            self.assertEqual([row["reason"] for row in waits], ["change", "change", "timeout"])

    def test_captain_runtime_configuration_is_validated_before_resource_creation(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.json"
            value = {
                "runtimes": {
                    "worker-a": {"kind": "codex"},
                    "worker-b": {"kind": "codex"},
                },
                "captain": {"kind": "claude", "args": "invalid"},
            }
            path.write_text(json.dumps(value))
            with self.assertRaises(ValueError):
                runner.load_config(path)

    def test_host_trace_rejects_self_report_and_changed_listener_identity(self):
        trace = {"source": "self_report", "events": []}
        with self.assertRaises(AssertionError):
            runner.validate_host_trace(trace)
        trace = {
            "source": "host_tool_trace",
            "events": [
                {
                    "kind": "yield",
                    "at": 1,
                    "invocation_id": "first",
                    "requested_ms": 60000,
                    "effective_ms": 30000,
                },
                {
                    "kind": "yield",
                    "at": 2,
                    "invocation_id": "second",
                    "requested_ms": 60000,
                    "effective_ms": 30000,
                },
            ],
        }
        with self.assertRaises(AssertionError):
            runner.validate_host_trace(trace)

    def test_post_turn_trace_requires_final_before_done_and_unprompted_handling(self):
        trace = {
            "source": "host_tool_trace",
            "events": [
                {"kind": "wait_start", "at": 0, "invocation_id": "one"},
                {"kind": "wait_done", "at": 2, "invocation_id": "one"},
                {"kind": "final", "at": 3},
                {"kind": "turn_start", "at": 4, "unprompted": True},
                {"kind": "handled", "at": 5, "event_key": "event-one"},
            ],
        }
        with self.assertRaises(AssertionError):
            runner.validate_host_trace(trace, post_turn=True)
        trace["events"][1]["at"] = 4
        trace["events"][2]["at"] = 2
        trace["events"][3]["at"] = 5
        trace["events"][4]["at"] = 6
        result = runner.validate_host_trace(trace, post_turn=True)
        self.assertEqual(result["post_turn"], "trace_order_verified")
        trace["events"][3]["unprompted"] = False
        with self.assertRaises(AssertionError):
            runner.validate_host_trace(trace, post_turn=True)

    def test_interjection_claim_cannot_replace_suspended_input_with_between_call_input(
        self,
    ):
        trace = {
            "source": "host_tool_trace",
            "interjection_claim": True,
            "mode": "foreground",
            "events": [
                {"kind": "wait_start", "at": 0, "invocation_id": "one"},
                {"kind": "interjection", "at": 1, "phase": "between_calls"},
            ],
        }
        with self.assertRaises(AssertionError):
            runner.validate_host_trace(trace)
        trace["events"].append(
            {"kind": "interjection", "at": 2, "phase": "suspended_tool"}
        )
        result = runner.validate_host_trace(trace)
        self.assertEqual(result["interjection"], "trace_phases_verified")


if __name__ == "__main__":
    unittest.main()
