"""Domain command contracts: stable identity and independent lifecycles."""

import copy
import unittest
from unittest.mock import patch

import test_lifecycle_operations as fixtures

from logbook_cli.adapters import herdr
from logbook_cli.cli import app
from logbook_cli.document import LbError


class DomainTest(unittest.TestCase):
    setUp = fixtures.OperationsTest.setUp
    call = fixtures.OperationsTest.call
    token = fixtures.OperationsTest.token
    state = fixtures.OperationsTest.state
    json_file = fixtures.OperationsTest.json_file

    def identify(self, text="Build @core", identity="build"):
        return self.call(
            "task",
            "identify",
            "log.md",
            "--stage",
            "Stage 01 Build",
            "--task",
            text,
            "--task-id",
            identity,
            "--expect-version",
            self.token(),
        )

    def transition(self, action, *args, identity="build", **kwargs):
        return self.call(
            "task",
            action,
            "log.md",
            identity,
            "--basis",
            "Reviewed decision",
            "--expect-version",
            self.token(),
            *args,
            **kwargs,
        )

    def task_view(self):
        return self.call("task", "show", "log.md", "build")["task"]

    def test_submission_acceptance_reopen_and_cancel(self):
        self.identify()
        self.transition("start")
        self.transition("accept", "--candidate", "a", code=4)
        self.json_file("result.json", {"candidate": "a", "evidence": ["test report"]})
        self.transition("record-result", "--input-file", "result.json")
        self.assertIn("- [/]", self.log.read_text())
        self.transition("accept", "--candidate", "b", code=4)
        self.transition("accept", "--candidate", "a")
        self.assertEqual(self.task_view()["status"], "accepted")
        self.transition("reopen")
        self.transition("cancel")
        self.assertEqual(self.task_view()["status"], "cancelled")
        self.transition("reopen")
        self.assertTrue(self.task_view()["consistent"])

    def test_identity_criteria_change_and_human_protection(self):
        self.identify()
        self.transition("start")
        self.json_file("result.json", {"candidate": "a", "evidence": ["test report"]})
        self.transition("record-result", "--input-file", "result.json")
        self.log.write_text(
            self.log.read_text().replace("Build @core", "Build revised @core")
        )
        self.assertEqual(self.task_view()["id"], "build")
        self.assertFalse(self.task_view()["evidence_applicable"])
        self.transition("accept", "--candidate", "a", code=4)
        self.identify("Review 👱", "review")
        self.transition("start", identity="review")
        self.transition("cancel", identity="review", code=4)

    def test_duplicate_identity_and_stale_write(self):
        self.identify()
        old = self.token()
        self.log.write_text(self.log.read_text() + "\nHuman note\n")
        self.call(
            "task",
            "start",
            "log.md",
            "build",
            "--basis",
            "decision",
            "--expect-version",
            old,
            code=4,
        )
        line = next(x for x in self.log.read_text().splitlines() if "<!-- lb-task" in x)
        self.log.write_text(self.log.read_text().replace(line, line + "\n" + line))
        self.call("task", "show", "log.md", "build", code=4)

    def dispatch_call(self, action, *args, **kwargs):
        return self.call(
            "dispatch",
            action,
            "log.md",
            "--thinking",
            "thinking.md",
            "--expect-version",
            self.token("thinking.md"),
            *args,
            **kwargs,
        )

    def test_dispatch_attempts_do_not_accept_task_and_pause_allows_return(self):
        self.state("active")
        self.identify()
        data = dict(
            id="d1",
            task_id="build",
            owner="sailor",
            scope="build",
            exclusions="publication",
            inputs="source",
            completion="tests pass",
            escalation="blocked",
        )
        self.json_file("dispatch.json", data)
        self.dispatch_call("create", "--input-file", "dispatch.json")
        self.dispatch_call("create", "--input-file", "dispatch.json", code=4)
        for status in ("sent", "acknowledged"):
            self.dispatch_call(
                "set-status", "d1", "--status", status, "--basis", "observed"
            )
        self.dispatch_call(
            "attempt", "d1", "a1", "--status", "started", "--basis", "observed"
        )
        self.dispatch_call(
            "set-status", "d1", "--status", "returned", "--basis", "observed", code=4
        )
        self.state("paused")
        self.dispatch_call(
            "attempt", "d1", "a1", "--status", "interrupted", "--basis", "observed"
        )
        self.dispatch_call(
            "attempt", "d1", "a2", "--status", "started", "--basis", "observed", code=4
        )
        self.dispatch_call(
            "set-status", "d1", "--status", "returned", "--basis", "observed"
        )
        self.dispatch_call(
            "set-status", "d1", "--status", "closed", "--basis", "observed"
        )
        self.assertEqual(self.task_view()["status"], "pending")
        self.assertEqual(self.thinking.read_text(), "# Thinking\n\nHuman notes stay.\n")
        from logbook_cli.state import path_for
        self.assertTrue(path_for(self.thinking, self.root).exists())

    def test_only_canonical_routes_are_exposed(self):
        self.assertEqual(
            set(app.commands),
            {
                "log",
                "task",
                "dispatch",
                "agent",
                "workflow",
                "skill",
                "feedback",
                "config",
            },
        )
        for route in (
            "context",
            "show",
            "next",
            "state",
            "sync",
            "check",
            "list",
            "run",
            "closeout",
            "retro",
            "runtime",
            "skills",
            "link",
        ):
            result = self.runner.invoke(app, [route, "--help"])
            self.assertEqual(result.exit_code, 2, route)
        for path in (
            ("workflow", "replace"),
            ("workflow", "instantiate"),
            ("log", "show"),
            ("log", "next"),
            ("log", "links", "verify"),
            ("log", "events", "metrics"),
            ("skill", "recipe"),
        ):
            self.assertEqual(self.runner.invoke(app, [*path, "--help"]).exit_code, 2)

        def inspect_commands(group):
            self.assertEqual(
                len(group.commands),
                len({id(command) for command in group.commands.values()}),
            )
            for command in group.commands.values():
                for parameter in command.params:
                    self.assertFalse(
                        {
                            "--token",
                            "--thinking-token",
                            "--event-file",
                            "--inputs",
                            "--input",
                        }.intersection(getattr(parameter, "opts", []))
                    )
                if hasattr(command, "commands"):
                    inspect_commands(command)

        inspect_commands(app)
        before = self.log.read_bytes()
        self.call("log", "sync", "log.md", "--token", self.token(), code=2)
        self.assertEqual(self.log.read_bytes(), before)

    def test_skill_usage_pins_definition_and_does_not_infer_adoption(self):
        self.identify()
        path = self.root / "skills/example/SKILL.md"
        path.parent.mkdir(parents=True)
        path.write_text("---\nversion: 1.0\n---\nExample")
        self.assertEqual(self.call("skill", "check", "example")["status"], "unknown")
        data = dict(
            id="u1",
            task_id="build",
            skill="example",
            state="declared",
            outcome="effective",
            basis="return",
            at="2026-01-01T00:00:00Z",
        )

        def record(code=0):
            self.json_file("usage.json", data)
            return self.call(
                "skill",
                "record-usage",
                "log.md",
                "--thinking",
                "thinking.md",
                "--input-file",
                "usage.json",
                "--expect-version",
                self.token("thinking.md"),
                code=code,
            )

        record(code=4)
        data["outcome"] = "unknown"
        first = record()["usage"]["definition_digest"]
        path.write_text("Changed definition")
        data.update(state="observed", outcome="effective")
        self.assertEqual(record()["usage"]["definition_digest"], first)
        data.update(state="declared", outcome="unknown")
        record(code=4)

    def test_workflow_availability_and_retirement(self):
        fixtures.OperationsTest.make_workflow(self)
        self.workflow_input = lambda: fixtures.OperationsTest.workflow_input(self)
        token = self.call("workflow", "show", "example")["version_token"]
        self.call(
            "workflow",
            "set-status",
            "example",
            "--status",
            "draft",
            "--basis",
            "review pending",
            "--expect-version",
            token,
        )
        token = self.call("workflow", "show", "example")["version_token"]
        args = (
            "log",
            "create",
            "created.md",
            "--from-workflow",
            "example",
            "--input-file",
            self.workflow_input(),
        )
        self.call(*args, "--expect-version", token, code=4)
        for status in ("available", "retired"):
            self.call(
                "workflow",
                "set-status",
                "example",
                "--status",
                status,
                "--basis",
                "decision",
                "--expect-version",
                token,
            )
            token = self.call("workflow", "show", "example")["version_token"]
            self.call(
                *args,
                "--expect-version",
                token,
                "--dry-run",
                code=0 if status == "available" else 4,
            )
        self.assertFalse((self.root / "created.md").exists())

    def test_config_diagnostics_reject_duplicate_and_unsafe_yaml(self):
        from logbook_cli.diagnostics import config_check

        path = self.root / "lbkit.yaml"
        path.write_text("version: 0.2.0\nsettings: {}\nagents: {}\n")
        self.assertTrue(config_check(self.root)["valid"])
        for text in (
            "version: 0.2.0\nversion: 0.1.0",
            "!!python/object/apply:os.system [echo unsafe]",
            "version: 0.2.0\nruntime: []",
        ):
            path.write_text(text)
            self.assertFalse(config_check(self.root)["valid"])

    def test_stale_accepted_evidence_blocks_log_completion(self):
        self.identify()
        self.transition("start")
        self.json_file("result.json", {"candidate": "a", "evidence": ["report"]})
        self.transition("record-result", "--input-file", "result.json")
        self.transition("accept", "--candidate", "a")
        self.log.write_text(
            self.log.read_text()
            .replace("Build @core", "Different @core")
            .replace("- [ ] Review", "- [x] Review")
        )
        self.call(
            "log",
            "state-set",
            "log.md",
            "--lifecycle",
            "completed",
            "--basis",
            "review",
            "--expect-version",
            self.token(),
            code=4,
        )

    def test_english_workflow_render(self):
        path = fixtures.OperationsTest.make_workflow(self)
        text = path.read_text()
        for old, new in [
            ("运行实例模板", "Run-instance template"),
            ("既定裁定", "Established rulings"),
            ("槽", "Slot"),
            ("标题：", "Title:"),
            ("工作目录：", "Working directories:"),
        ]:
            text = text.replace(old, new)
        path.write_text(text)
        self.call(
            "workflow",
            "render",
            "example",
            "--input-file",
            fixtures.OperationsTest.workflow_input(self),
            "--expect-version",
            self.call("workflow", "show", "example")["version_token"],
        )


class RuntimeTest(unittest.TestCase):
    def native_snapshot(self):
        binding = dict(
            machine="local",
            workspace_id="w1",
            tab_id="w1:t1",
            pane_id="w1:p1",
            agent_id="reviewer",
            session_id="session-a",
        )
        pane = dict(
            workspace_id="w1",
            tab_id="w1:t1",
            pane_id="w1:p1",
            agent="codex",
            agent_status="idle",
            terminal_id="term-example",
            agent_session=dict(
                kind="id", value="session-a", agent="codex", source="herdr:codex"
            ),
        )
        agent = {**copy.deepcopy(pane), "name": "reviewer"}
        return binding, pane, agent

    def snapshot_reader(self, pane, agent):
        def invoke(machine, *args, **kwargs):
            self.assertEqual(machine, "local")
            self.assertFalse(kwargs.get("mutation"), "unexpected runtime effect")
            if args[:2] == ("pane", "get"):
                return {"result": {"pane": pane}}
            if args[:2] == ("agent", "get"):
                return {"result": {"agent": agent}}
            self.assertEqual(args[:2], ("pane", "read"))
            return "Ready for input"

        return invoke

    def test_native_herdr_session_reference_supports_live_control(self):
        binding, pane, agent = self.native_snapshot()
        reader = self.snapshot_reader(pane, agent)
        with patch.object(herdr, "invoke", side_effect=reader):
            observed = herdr.inspect(binding)
        self.assertTrue(observed["live_verified"])
        self.assertEqual(observed["observation"]["session_id"], "session-a")
        journal = unittest.mock.Mock()

        def transport(machine, *args, **kwargs):
            if kwargs.get("mutation"):
                journal.assert_called_once()
                self.assertEqual(args, ("agent", "prompt", "w1:p1", "review only"))
                return {"result": {"type": "agent_prompted"}}
            return reader(machine, *args, **kwargs)

        with patch.object(herdr, "invoke", side_effect=transport):
            result = herdr.control(
                binding,
                "send",
                "session-a",
                observed["observation_token"],
                "review only",
                False,
                before_mutation=journal,
            )
        self.assertEqual(result["receipt"]["result"]["type"], "agent_prompted")

    def test_missing_conflicting_and_wrong_agent_session_references_refuse(self):
        for variant in (
            "missing",
            "conflict",
            "wrong-agent",
            "path",
            "empty",
            "malformed",
            "flat-conflict",
        ):
            with self.subTest(variant=variant):
                binding, pane, agent = self.native_snapshot()
                if variant == "missing":
                    pane.pop("agent_session")
                    agent.pop("agent_session")
                elif variant == "conflict":
                    agent["agent_session"]["value"] = "session-b"
                elif variant == "wrong-agent":
                    agent["agent_session"]["agent"] = "another-agent"
                elif variant == "path":
                    agent["agent_session"].update(kind="path", value="/example/session")
                elif variant == "empty":
                    agent["agent_session"]["value"] = ""
                elif variant == "malformed":
                    agent["agent_session"] = "session-a"
                else:
                    agent["session_id"] = "session-b"
                journal = unittest.mock.Mock()
                with patch.object(
                    herdr, "invoke", side_effect=self.snapshot_reader(pane, agent)
                ):
                    observed = herdr.inspect(binding)
                    self.assertFalse(observed["live_verified"])
                    self.assertTrue(observed["capability_gap"])
                    with self.assertRaises(LbError):
                        herdr.control(
                            binding,
                            "send",
                            "session-a",
                            observed["observation_token"],
                            "review",
                            False,
                            before_mutation=journal,
                        )
                journal.assert_not_called()

    def test_session_replacement_in_same_pane_invalidates_previous_observation(self):
        binding, pane, agent = self.native_snapshot()
        with patch.object(
            herdr, "invoke", side_effect=self.snapshot_reader(pane, agent)
        ):
            before = herdr.inspect(binding)
            pane["agent_session"]["value"] = "session-b"
            agent["agent_session"]["value"] = "session-b"
            after = herdr.inspect(binding)
            self.assertFalse(after["live_verified"])
            self.assertIn("session_id", after["mismatches"])
            self.assertNotEqual(before["observation_token"], after["observation_token"])
            with self.assertRaises(LbError):
                herdr.control(
                    binding,
                    "send",
                    "session-a",
                    before["observation_token"],
                    "review",
                    False,
                )

    def test_native_single_surface_and_legacy_flat_session_are_supported(self):
        for surface in ("pane", "agent", "legacy"):
            with self.subTest(surface=surface):
                binding, pane, agent = self.native_snapshot()
                if surface == "pane":
                    agent.pop("agent_session")
                elif surface == "agent":
                    pane.pop("agent_session")
                else:
                    pane.pop("agent_session")
                    agent.pop("agent_session")
                    agent["session_id"] = "session-a"
                with patch.object(
                    herdr, "invoke", side_effect=self.snapshot_reader(pane, agent)
                ):
                    self.assertTrue(herdr.inspect(binding)["live_verified"])

    def test_binding_requires_full_handles(self):
        item = dict(
            machine="local",
            workspace_id="w1",
            tab_id="w1:t9",
            pane_id="w1:p7",
            agent_id="builder",
            session_id="s",
            observed_at="2026-01-01T00:00:00Z",
            basis="runtime read",
        )
        self.assertEqual(herdr.validate_binding(item), item)
        for key, value in (
            ("workspace_id", "1"),
            ("tab_id", "9"),
            ("pane_id", "w2:p7"),
        ):
            with self.assertRaises(LbError):
                herdr.validate_binding({**item, key: value})

    def test_unknown_session_refuses_control(self):
        with (
            patch.object(herdr, "inspect", return_value={"live_verified": False}),
            patch.object(herdr, "invoke") as invoke,
        ):
            with self.assertRaises(LbError):
                herdr.control({"session_id": "s"}, "send", "s", "o", "hello", False)
            invoke.assert_not_called()

    def test_preview_and_one_shot_transport(self):
        observation = {
            "live_verified": True,
            "observation_token": "o",
            "observation": {"state": "idle"},
        }
        binding = {"session_id": "s", "pane_id": "p", "machine": "local"}
        with (
            patch.object(herdr, "inspect", return_value=observation),
            patch.object(herdr, "invoke", return_value={}) as invoke,
        ):
            herdr.control(binding, "send", "s", "o", "hello", True)
            invoke.assert_not_called()
            herdr.control(binding, "send", "s", "o", "hello", False)
            invoke.assert_called_once_with(
                "local", "agent", "prompt", "p", "hello", mutation=True
            )
            invoke.reset_mock()
            herdr.control(binding, "close", "s", "o", None, False)
            invoke.assert_called_once_with("local", "pane", "close", "p", mutation=True)
