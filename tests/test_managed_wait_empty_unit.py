import unittest
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import patch

from logbook_cli.services import agent_wait


class EmptyWaitTests(unittest.TestCase):
    def test_no_targets_without_runtime_or_mutation(self):
        value = {"targets": [], "cursors": [], "events": [], "answers": []}
        with (
            patch("logbook_cli.services.common.load", return_value=SimpleNamespace()),
            patch("logbook_cli.observation.read", return_value=(value, "t")),
            patch("logbook_cli.observation.listener_lock", return_value=nullcontext()),
            patch.object(agent_wait, "observe_all") as runtime,
            patch("logbook_cli.observation._change") as change,
        ):
            result = agent_wait.managed_wait(".", "work.md", 1, "t", False)
        self.assertEqual(result.value["reason"], "no_targets")
        self.assertIsNone(result.value["invocation_id"])
        runtime.assert_not_called()
        change.assert_not_called()

    def test_raw_empty_rejected(self):
        with self.assertRaises(ValueError):
            agent_wait.validate({"targets": []})
