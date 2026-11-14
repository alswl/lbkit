"""Herdr adapter behavior with all transport replaced by mocks."""

import copy
import unittest
from unittest.mock import patch

from logbook_cli.adapters import herdr
from logbook_cli.document import LbError


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
