"""Exercise existing open through Click with recorded native operations."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from logbook_cli.cli import app


class OpenLabelPolicyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.root.joinpath("lbkit.yaml").write_text(
            json.dumps(
                {
                    "version": "0.2.0",
                    "settings": {
                        "runtime": {
                            "herdr": {
                                "label_prefix": "qa-",
                            }
                        }
                    },
                    "agents": {},
                }
            )
        )
        self.root.joinpath("open.json").write_text(
            json.dumps(
                {
                    "machine": "local",
                    "server": "default",
                    "parent_pane": "w1:p9",
                    "cwd": str(self.root),
                    "runtime": "codex",
                    "name": "reviewer",
                }
            )
        )
        self.calls = []
        self.label = "shell"
        self.mismatch = False

    def native(self, machine, *args, **kwargs):
        self.calls.append((machine, args, kwargs))
        if args[0] == "status":
            return {"server": {"running": True, "session": "default"}}
        pane = {
            "pane_id": "w1:p2",
            "workspace_id": "w1",
            "tab_id": "w1:t2",
            "cwd": str(self.root),
            "label": self.label,
            "agent": "codex",
            "session_id": "fixture-session",
        }
        if args[:2] == ("pane", "rename") and not self.mismatch:
            self.label = args[-1]
        agent = {**pane, "name": "reviewer", "agent_status": "idle"}
        return {"result": {"pane": pane, "agent": agent}}

    def invoke(self):
        with patch("logbook_cli.adapters.herdr.invoke", side_effect=self.native):
            return CliRunner().invoke(
                app,
                [
                    "--root",
                    str(self.root),
                    "agent",
                    "herdr",
                    "open",
                    "--input-file",
                    "open.json",
                    "--json",
                ],
            )

    def test_open_consumes_prefix_before_start_without_changing_logical_id(self):
        result = self.invoke()
        self.assertEqual(result.exit_code, 0, result.output)
        commands = [c[1] for c in self.calls]
        rename = ("pane", "rename", "w1:p2", "qa-reviewer")
        self.assertIn(rename, commands)
        start = next(c for c in commands if c[:2] == ("agent", "start"))
        self.assertEqual(start[2], "reviewer")
        self.assertLess(commands.index(rename), commands.index(start))
        self.assertIn(
            "--no-focus", next(c for c in commands if c[:2] == ("pane", "split"))
        )
        self.assertEqual(
            json.loads(result.stdout)["display_policy"]["status"], "verified"
        )

    def test_mismatch_retains_created_id_without_start_or_second_allocation(self):
        self.mismatch = True
        result = self.invoke()
        self.assertEqual(result.exit_code, 1, result.output)
        value = json.loads(result.stdout)
        self.assertEqual(value["owned_panes"], ["w1:p2"])
        self.assertEqual(value["display_policy"]["resource_id"], "w1:p2")
        commands = [c[1][:2] for c in self.calls]
        self.assertEqual(commands.count(("pane", "split")), 1)
        self.assertNotIn(("agent", "start"), commands)

    def test_invalid_prefix_refuses_before_allocation(self):
        value = json.loads(self.root.joinpath("lbkit.yaml").read_text())
        value["settings"]["runtime"]["herdr"]["label_prefix"] = ["invalid"]
        self.root.joinpath("lbkit.yaml").write_text(json.dumps(value))
        result = self.invoke()
        self.assertNotEqual(result.exit_code, 0)
        self.assertFalse(any(c[1][:2] == ("pane", "split") for c in self.calls))
