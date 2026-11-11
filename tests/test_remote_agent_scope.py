"""Remote API forwarding regressions using an offline executable only."""

import json

from coordination_helpers import CoordinationTest
from test_agent_wait_e2e import observation, target


class RemoteAgentScopeTest(CoordinationTest):
    def runtime(
        self, state="idle", *, session="example-session", code=0, changed=False
    ):
        self.item = target()
        self.item["binding"]["machine"] = "example-remote"
        live = observation(self.item, state)
        if changed:
            live["session_id"] = "replacement"
            live["agent_session"]["value"] = "replacement"
        live["foreground_cwd"] = str(self.root)
        profile = {
            "id": "machine-example",
            "label": "example-remote",
            "session": session,
            "enabled": True,
        }
        self.rules = [
            {
                "argv": ["--machine", "example-remote", "status"],
                "responses": [{"code": 2}],
            },
            {
                "argv": ["machine", "list", "--json"],
                "responses": [{"stdout": [profile]}],
            },
        ]
        for command in (
            ["pane", "get"],
            ["agent", "get"],
            ["agent", "wait"],
            ["pane", "split"],
            ["agent", "start"],
            ["pane", "close"],
            ["pane", "list"],
        ):
            self.rules.append(
                {
                    "argv": ["--machine", "machine-example", *command],
                    "responses": [
                        {
                            "code": code,
                            "stdout": {
                                "result": {"pane": live, "agent": live, "panes": []}
                            },
                        }
                    ],
                }
            )
        self.script(self.rules)
        return live

    def wait(self, timeout="1", code=0):
        self.identify()
        (self.root / "targets.json").write_text(json.dumps({"targets": [self.item]}))
        context = self.cli("agent", "observation", "context", "log.md")
        self.cli(
            "agent",
            "observation",
            "configure",
            "log.md",
            "--input-file",
            "targets.json",
            "--expect-version",
            context["version_token"],
        )
        context = self.cli("agent", "observation", "context", "log.md")
        return self.cli(
            "agent",
            "wait",
            "--log",
            "log.md",
            "--timeout",
            timeout,
            "--expect-version",
            context["version_token"],
            code=code,
        )

    def starts(self):
        return [r["argv"] for r in self.calls() if r["kind"] == "start"]

    def test_remote_idle_and_done_reach_observation(self):
        for state in ("idle", "done"):
            with self.subTest(state=state):
                self.runtime(state)
                # Raw and managed use the same observer; managed persistence is
                # covered independently below to keep this two-state test small.
                (self.root / "wait.json").write_text(
                    json.dumps({"targets": [self.item]})
                )
                result = self.cli(
                    "agent", "wait", "--input-file", "wait.json", "--timeout", "1"
                )
                self.assertEqual([e["kind"] for e in result["events"]], ["settled"])

    def test_managed_remote_completion_is_durable(self):
        self.runtime()
        result = self.wait()
        self.assertEqual(
            [e["observation"]["kind"] for e in result["new_events"]], ["settled"]
        )
        context = self.cli("agent", "observation", "context", "log.md")
        self.assertEqual(context["unresolved_events"], result["new_events"])
        self.assertNotIn("status", sum(self.starts(), []))

    def test_remote_working_to_done(self):
        live = self.runtime("working")
        for rule in self.rules:
            if rule["argv"][-2:] == ["agent", "get"]:
                done = {**live, "agent_status": "done"}
                rule["responses"].append({"stdout": {"result": {"agent": done}}})
        self.script(self.rules)
        result = self.wait("3")
        self.assertEqual(
            [e["observation"]["kind"] for e in result["new_events"]], ["settled"]
        )
        self.assertTrue(any("wait" in args for args in self.starts()))

    def test_remote_native_identity_change_is_reported(self):
        self.runtime(changed=True)
        result = self.wait()
        self.assertEqual(
            [e["observation"]["kind"] for e in result["new_events"]],
            ["identity_changed"],
        )

    def lifecycle(self, action, code=0):
        value = (
            {
                "machine": "example-remote",
                "server": "example-session",
                "parent_pane": "w1:p1",
                "cwd": str(self.root),
                "runtime": "codex",
                "name": "example-worker",
            }
            if action == "open"
            else {"binding": self.item["binding"], "owned_panes": ["w1:p1"]}
        )
        (self.root / "request.json").write_text(json.dumps(value))
        return self.cli("agent", action, "--input-file", "request.json", code=code)

    def test_remote_lifecycle_uses_selected_profile(self):
        self.runtime()
        opened = self.lifecycle("open")
        self.assertEqual(opened["binding"], self.item["binding"])
        self.assertEqual(self.lifecycle("close-session")["status"], "closed")
        starts = self.starts()
        self.assertNotIn("status", sum(starts, []))
        self.assertTrue(
            all(
                args[:2] == ["--machine", "machine-example"]
                for args in starts
                if args[0] != "machine"
            )
        )

    def test_remote_failures_never_fall_back_or_mutate(self):
        for options in ({"session": "other-server"}, {"code": 1}):
            with self.subTest(options=options):
                self.runtime(**options)
                (self.root / "wait.json").write_text(
                    json.dumps({"targets": [self.item]})
                )
                result = self.cli(
                    "agent",
                    "wait",
                    "--input-file",
                    "wait.json",
                    "--timeout",
                    "1",
                    code=1,
                )
                self.assertEqual(
                    [e["kind"] for e in json.loads(result.stdout)["events"]],
                    ["unavailable"],
                )
                for action in ("open", "close-session"):
                    self.lifecycle(action, code=4)
                self.assertFalse(
                    any(
                        x in sum(self.starts(), []) for x in ("split", "start", "close")
                    )
                )

    def test_remote_profile_gaps_refuse_before_api_calls(self):
        self.runtime()
        profile = self.rules[1]["responses"][0]["stdout"][0]
        for profiles in (
            [],
            [dict(profile, enabled=False)],
            [dict(profile, session=None)],
            [dict(profile, id="local")],
            [profile, dict(profile, id="another-profile")],
            ["malformed"],
        ):
            with self.subTest(profiles=profiles):
                self.rules[1]["responses"] = [{"stdout": profiles}]
                self.script(self.rules)
                (self.fake / "calls.jsonl").unlink(missing_ok=True)
                (self.root / "wait.json").write_text(
                    json.dumps({"targets": [self.item]})
                )
                result = self.cli(
                    "agent",
                    "wait",
                    "--input-file",
                    "wait.json",
                    "--timeout",
                    "1",
                    code=1,
                )
                self.assertEqual(
                    json.loads(result.stdout)["events"][0]["kind"], "unavailable"
                )
                self.assertEqual(self.starts(), [["machine", "list", "--json"]])

    def test_remote_profile_id_selector_is_supported(self):
        self.runtime()
        self.item["binding"]["machine"] = "machine-example"
        (self.root / "wait.json").write_text(json.dumps({"targets": [self.item]}))
        result = self.cli(
            "agent", "wait", "--input-file", "wait.json", "--timeout", "1"
        )
        self.assertEqual(result["events"][0]["kind"], "settled")

    def test_remote_replacement_refuses_close_before_mutation(self):
        self.runtime(changed=True)
        self.lifecycle("close-session", code=4)
        self.assertFalse(any("close" in args for args in self.starts()))
