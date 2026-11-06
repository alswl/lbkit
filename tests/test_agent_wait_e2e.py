"""One-shot wait public contract, executed only against the offline Herdr fixture."""

import json
import os
import time

from coordination_helpers import CoordinationTest


def target(number=1, state="working"):
    return {
        "binding": {
            "machine": "local",
            "server": "example-session",
            "workspace_id": "w1",
            "tab_id": "w1:t1",
            "pane_id": f"w1:p{number}",
            "agent_id": "codex",
            "session_id": f"example-native-{number}",
        },
        "baseline": {"state": state, "observed_at": "2026-01-01T00:00:00Z"},
    }


def observation(item, state):
    binding = item["binding"]
    return {
        **binding,
        "id": binding["pane_id"],
        "state": state,
        "status": state,
        "agent": binding["agent_id"],
        "agent_status": state,
        "workspace": binding["workspace_id"],
        "tab": binding["tab_id"],
        "agent_session": {
            "kind": "id",
            "source": "fixture",
            "agent": binding["agent_id"],
            "value": binding["session_id"],
        },
    }


class AgentWaitE2ETest(CoordinationTest):
    def request(self, targets=None, after=None):
        value = {
            "targets": targets if targets is not None else [target()],
            "after": after,
        }
        (self.root / "wait.json").write_text(json.dumps(value))
        return value

    def runtime(self, targets, states, delay=0):
        rules = [
            {
                "argv": ["status"],
                "responses": [
                    {
                        "stdout": {
                            "server": {"running": True, "session": "example-session"}
                        }
                    }
                ],
            }
        ]
        for item, state in zip(targets, states):
            pane = item["binding"]["pane_id"]
            for command in (["agent", "get"], ["pane", "get"], ["agent", "wait"]):
                rules.append(
                    {
                        "argv": command,
                        "target": pane,
                        "responses": [
                            {
                                "stdout": {
                                    "result": {
                                        "agent": observation(item, state),
                                        "pane": observation(item, state),
                                    }
                                },
                                "delay": delay if command[-1] == "wait" else 0,
                            }
                        ],
                    }
                )
        self.script(rules)

    def wait(self, timeout="0.3", code=0):
        return self.cli(
            "agent",
            "wait",
            "--input-file",
            "wait.json",
            "--timeout",
            timeout,
            code=code,
            timeout=5,
        )

    def assert_no_runtime_mutations_or_leaks(self):
        for row in self.calls():
            args = row["argv"]
            self.assertFalse(
                any(x in args for x in ("prompt", "send", "close", "stop", "start"))
            )
            self.assertNotIn("read", args, "No terminal transcript heartbeat")
            if row["kind"] == "start":
                with self.assertRaises(ProcessLookupError):
                    os.kill(row["pid"], 0)

    def test_timeout_returns_reusable_input_without_writes(self):
        targets = [target()]
        self.runtime(targets, ["working"], delay=0.05)
        self.request(targets)
        before = self.snapshot()
        result = self.wait()
        self.assertEqual(result["reason"], "timeout")
        self.assertEqual(result["events"], [])
        self.assertEqual(
            result["next_input"]["targets"][0]["binding"], targets[0]["binding"]
        )
        self.assertEqual(before, self.snapshot())
        self.assert_no_runtime_mutations_or_leaks()

    def test_immediate_native_wait_does_not_busy_poll(self):
        self.runtime([target()], ["working"])
        self.request()
        result = self.wait("1")
        self.assertEqual(result["reason"], "timeout")
        starts = [row for row in self.calls() if row["kind"] == "start"]
        self.assertLessEqual(len(starts), 4)
        self.assert_no_runtime_mutations_or_leaks()

    def test_any_target_returns_attention_and_preserves_other_pending(self):
        targets = [target(1), target(2)]
        self.runtime(targets, ["working", "blocked"], delay=0.05)
        self.request(targets)
        result = self.wait("1")
        self.assertEqual(result["reason"], "change")
        self.assertTrue(
            any(
                e["kind"] == "needs_input" and e["binding"] == targets[1]["binding"]
                for e in result["events"]
            )
        )
        self.assertIn(targets[0]["binding"], result["pending"])
        self.assert_no_runtime_mutations_or_leaks()

    def test_attention_after_first_four_working_targets_is_not_starved(self):
        targets = [target(n) for n in range(1, 6)]
        self.runtime(targets, ["working"] * 4 + ["blocked"], delay=0.05)
        self.request(targets)
        result = self.wait("2")
        self.assertEqual(result["reason"], "change")
        self.assertTrue(
            any(
                e["kind"] == "needs_input" and e["binding"] == targets[4]["binding"]
                for e in result["events"]
            )
        )
        self.assertEqual(result["pending"], [t["binding"] for t in targets[:4]])
        self.assert_no_runtime_mutations_or_leaks()

    def test_continuation_suppresses_same_blocked_observation(self):
        targets = [target()]
        self.runtime(targets, ["blocked"])
        self.request(targets)
        first = self.wait("1")
        self.assertEqual([e["kind"] for e in first["events"]], ["needs_input"])
        (self.root / "wait.json").write_text(json.dumps(first["next_input"]))
        second = self.wait()
        self.assertFalse(any(e["kind"] == "needs_input" for e in second["events"]))
        self.assertEqual(second["unresolved_events"], first["events"])
        self.assertEqual(second["next_input"]["unresolved_events"], first["events"])
        self.assert_no_runtime_mutations_or_leaks()

    def test_handled_event_can_be_removed_without_rearming_notification(self):
        self.runtime([target()], ["blocked"])
        self.request()
        first = self.wait("1")
        request = first["next_input"]
        self.assertEqual(request["unresolved_events"], first["events"])
        # Caller has saved and verified its handling receipt outside this read API.
        request["unresolved_events"] = []
        (self.root / "wait.json").write_text(json.dumps(request))
        second = self.wait()
        self.assertEqual(second["events"], [])
        self.assertEqual(second["unresolved_events"], [])

    def test_unresolved_event_from_other_binding_is_rejected(self):
        self.runtime([target()], ["blocked"])
        self.request()
        first = self.wait("1")
        request = first["next_input"]
        request["unresolved_events"] = first["events"]
        request["unresolved_events"][0]["binding"] = target(2)["binding"]
        (self.root / "wait.json").write_text(json.dumps(request))
        self.wait(code=2)

    def test_unhandled_question_survives_other_worker_result_and_resume(self):
        targets = [target(1), target(2)]
        self.runtime(targets, ["blocked", "working"])
        self.request(targets)
        first = self.wait("1")
        question = next(e for e in first["events"] if e["kind"] == "needs_input")
        # Simulate a new caller turn reading only the durable complete checkpoint.
        (self.root / "wait.json").write_text(json.dumps(first["next_input"]))
        self.runtime(targets, ["blocked", "idle"])
        second = self.wait("1")
        self.assertIn(question, second["unresolved_events"])
        self.assertNotIn(question, second["events"])
        self.assertTrue(any(e["kind"] == "settled" for e in second["events"]))
        self.assertEqual(second["next_input"]["targets"], targets)
        self.assert_no_runtime_mutations_or_leaks()

    def test_duplicate_checkpoint_event_is_not_duplicated_or_renotified(self):
        self.runtime([target()], ["blocked"])
        self.request()
        first = self.wait("1")
        request = first["next_input"]
        request["unresolved_events"] *= 2
        (self.root / "wait.json").write_text(json.dumps(request))
        second = self.wait()
        self.assertEqual(second["events"], [])
        self.assertEqual(second["unresolved_events"], first["events"])

    def test_full_or_conflicting_checkpoint_is_refused_before_observation(self):
        event = {
            "event_id": "old-question",
            "binding": target()["binding"],
            "kind": "needs_input",
        }
        for events in (
            [{**event, "event_id": str(i)} for i in range(256)],
            [event, {**event, "kind": "settled"}],
            [{**event, "event_id": None}],
        ):
            request = self.request()
            request["unresolved_events"] = events
            (self.root / "wait.json").write_text(json.dumps(request))
            self.wait(code=2)
            self.assertEqual(self.calls(), [])

    def test_old_idle_seen_flip_does_not_claim_completed_work(self):
        targets = [target(state="idle")]
        self.runtime(targets, ["done"])
        self.request(targets)
        result = self.wait()
        self.assertFalse(any(e["kind"] == "settled" for e in result["events"]))
        self.assert_no_runtime_mutations_or_leaks()

    def test_changed_native_identity_is_not_rebound(self):
        original = target()
        changed = target()
        changed["binding"]["session_id"] = "example-replacement"
        self.runtime([changed], ["idle"])
        self.request([original])
        result = self.wait("1")
        self.assertIn("identity_changed", [e["kind"] for e in result["events"]])
        self.assertNotIn("settled", [e["kind"] for e in result["events"]])

    def test_global_deadline_includes_queued_workers(self):
        targets = [target(n) for n in range(1, 13)]
        self.runtime(targets, ["working"] * len(targets), delay=10)
        self.request(targets)
        started = time.monotonic()
        result = self.wait()
        self.assertLess(time.monotonic() - started, 3.3)
        self.assertEqual(result["reason"], "timeout")
        self.assert_no_runtime_mutations_or_leaks()

    def test_invalid_requests_fail_before_starting_children(self):
        for targets in ([], [target(n) for n in range(65)]):
            with self.subTest(count=len(targets)):
                self.request(targets)
                before = self.snapshot()
                result = self.wait(code=2)
                self.assertNotIn("No such command", result.stderr)
                self.assertEqual(before, self.snapshot())
                self.assertEqual(self.calls(), [])

    def test_invalid_timeout_is_usage_error_not_missing_route(self):
        self.request()
        for timeout in ("0", "-1", "nan", "inf"):
            with self.subTest(timeout=timeout):
                result = self.wait(timeout, code=2)
                self.assertNotIn("No such command", result.stderr)
                self.assertEqual(self.calls(), [])

    def test_input_size_and_conflicting_duplicates_are_bounded(self):
        original = target()
        duplicate = target()
        duplicate["binding"]["session_id"] = "different-session"
        for request in (
            {"targets": [original, duplicate], "after": None},
            {"targets": [original], "after": "x" * (1024 * 1024)},
        ):
            (self.root / "wait.json").write_text(json.dumps(request))
            result = self.wait(code=2)
            self.assertNotIn("No such command", result.stderr)
            self.assertLess(len(result.stderr) + len(result.stdout), 1024 * 1024)
            self.assertEqual(self.calls(), [])

    def test_partial_unavailable_preserves_healthy_pending_target(self):
        targets = [target(1), target(2)]
        self.runtime(targets, ["working", "working"])
        script = json.loads((self.fake / "script.json").read_text())
        for rule in script["rules"]:
            if rule.get("target") == "w1:p1":
                rule["responses"] = [{"code": 1, "stderr": "unavailable"}]
        self.script(script["rules"])
        self.request(targets)
        result = self.wait("1")
        self.assertEqual(result["reason"], "change")
        self.assertIn("unavailable", [e["kind"] for e in result["events"]])
        self.assertNotIn("exited", [e["kind"] for e in result["events"]])
        self.assertIn(targets[1]["binding"], result["pending"])
        self.assert_no_runtime_mutations_or_leaks()

    def test_interrupt_returns_130_and_reaps_wait_children(self):
        import signal
        import subprocess
        import sys

        from coordination_helpers import REPO

        targets = [target(), target(2)]
        self.runtime(targets, ["blocked", "working"])
        self.request(targets)
        first = self.wait("1")
        self.assertTrue(first["unresolved_events"])
        (self.root / "wait.json").write_text(json.dumps(first["next_input"]))
        self.runtime(targets, ["blocked", "working"], delay=10)
        previous_calls = len(self.calls())
        process = subprocess.Popen(
            [
                sys.executable,
                str(REPO / "bin/lb"),
                "--root",
                str(self.root),
                "agent",
                "wait",
                "--input-file",
                "wait.json",
                "--timeout",
                "10",
                "--json",
            ],
            cwd=self.root,
            env=self.env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        try:
            limit = time.monotonic() + 2
            while (
                process.poll() is None
                and len(self.calls()) == previous_calls
                and time.monotonic() < limit
            ):
                time.sleep(0.02)
            self.assertIsNone(
                process.poll(), "Wait must be running before interruption"
            )
            process.send_signal(signal.SIGINT)
            stdout, stderr = process.communicate(timeout=3)
            self.assertEqual(process.returncode, 130, stderr)
            result = json.loads(stdout)
            self.assertEqual(result["reason"], "interrupted")
            self.assertEqual(result["unresolved_events"], first["events"])
            self.assertEqual(result["next_input"]["targets"], targets)
            self.assert_no_runtime_mutations_or_leaks()
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
            process.communicate(timeout=2)

    def test_large_ready_batch_retains_overflow_in_complete_continuation(self):
        targets = [target(n) for n in range(1, 41)]
        self.runtime(targets, ["blocked"] * len(targets))
        self.request(targets)
        seen = set()
        for _ in range(40):
            result = self.wait("1")
            self.assertLessEqual(len(result["events"]), 32)
            self.assertLessEqual(len(json.dumps(result).encode()), 1024 * 1024)
            next_input = result["next_input"]
            self.assertEqual(len(next_input["targets"]), len(targets))
            for event in result["events"]:
                if event["kind"] == "needs_input":
                    identity = event["binding"]["session_id"]
                    self.assertNotIn(identity, seen)
                    seen.add(identity)
            (self.root / "wait.json").write_text(json.dumps(next_input))
            if len(seen) == len(targets):
                break
        self.assertEqual(
            len(seen), len(targets), "Ready observations lost across continuation"
        )
        self.assert_no_runtime_mutations_or_leaks()
