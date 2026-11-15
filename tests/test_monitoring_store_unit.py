import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from logbook_cli import observation


class MonitoringTests(unittest.TestCase):
    def test_first_empty_configuration_is_complete(self):
        doc = SimpleNamespace(metadata={"document": {"identity": {"uuid": "a" * 32}}})
        with (
            patch.object(observation, "_snapshot", return_value=(None, "token", None)),
            patch.object(observation, "scope", return_value=Path("/repo/lb/work.json")),
        ):
            result = observation._configure(doc, [], [], "token", True)
        value = result["observation"]
        self.assertEqual(value["targets"], [])
        self.assertEqual(value["cursors"], [])
        self.assertEqual(value["retired"], {})
        self.assertEqual(value["revision"], 1)
        observation.validate(value)
