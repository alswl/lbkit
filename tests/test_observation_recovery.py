"""Recovery and handler/observer overlap, positioned by explicit pipe barriers."""

import json
import os
import select
import subprocess
import sys
from unittest.mock import patch

from click.testing import CliRunner
from coordination_helpers import REPO
from observation_fixtures import target
from test_observation_events import EventCase

from logbook_cli import storage
from logbook_cli.cli import main
from logbook_cli.commands import domains


class ObservationRecoveryTest(EventCase):
    def invoke_wait(self):
        token = self.context()["version_token"]
        with CliRunner().isolation() as streams:
            with patch.dict(os.environ, self.env):
                code = main(
                    [
                        "--root",
                        str(self.root),
                        "agent",
                        "wait",
                        "--log",
                        "log.md",
                        "--timeout",
                        "2",
                        "--expect-version",
                        token,
                        "--json",
                    ]
                )
            sys.stdout.flush()
            output = streams[0].getvalue()
        return code, output

    def test_failure_before_commit_keeps_prior_cursor_and_no_durable_event(self):
        self.setup_observation()
        self.runtime([target()], ["blocked"])
        replace = storage.replace_bytes_at

        def fail_event(directory, name, data, expected):
            if json.loads(data)["events"]:
                raise OSError("injected failure before event publication")
            return replace(directory, name, data, expected)

        with patch.object(storage, "replace_bytes_at", side_effect=fail_event):
            code, output = self.invoke_wait()
        self.assertEqual(code, 3)
        self.assertEqual(output, b"")
        saved = self.context()["observation"]
        self.assertEqual(saved["events"], [])
        self.assertIsNone(saved["contexts"][0]["reported"])
        self.assertEqual(saved["listener"]["status"], "ended")
        self.assertEqual(len(self.managed_wait()["new_events"]), 1)

    def test_lost_result_after_commit_recovers_same_question_without_renotification(
        self,
    ):
        self.setup_observation()
        self.runtime([target()], ["blocked"])
        with patch.object(
            domains, "finish", side_effect=OSError("injected lost stdout")
        ):
            code, output = self.invoke_wait()
        self.assertEqual(code, 3)
        self.assertEqual(output, b"")
        saved = self.context()["observation"]
        self.assertEqual(len(saved["events"]), 1)
        event = saved["events"][0]
        self.assertEqual(saved["contexts"][0]["reported"], "needs_input")
        again = self.managed_wait(timeout="0.3")
        self.assertEqual(again["new_events"], [])
        self.assertEqual(again["unresolved_events"], [event])

    def test_observer_delta_preserves_concurrent_deferral_and_other_worker(self):
        targets = [target(1), target(2)]
        self.setup_observation(targets)
        self.runtime(targets, ["blocked", "blocked"])
        gates = {command: self.barrier(command) for command in ("agent", "pane")}
        script = json.loads((self.fake / "script.json").read_text())
        for rule in script["rules"]:
            if rule.get("target") == "w1:p2" and rule["argv"] in (
                ["agent", "get"],
                ["pane", "get"],
            ):
                rule["responses"][0]["barriers"] = {"before_receipt": rule["argv"][0]}
        self.script(script["rules"])
        child = subprocess.Popen(
            [
                sys.executable,
                str(REPO / "bin/lb"),
                "--root",
                str(self.root),
                "agent",
                "wait",
                "--log",
                "log.md",
                "--stream",
                "--timeout",
                "4",
                "--expect-version",
                self.context()["version_token"],
                "--json",
            ],
            env=self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
        try:
            self.assertTrue(select.select([child.stdout], [], [], 3)[0])
            notice = json.loads(child.stdout.readline())
            first = self.context()["observation"]["events"][0]
            self.assertEqual(first["id"], notice["event_key"])
            self.assertEqual(first["observation"]["binding"]["pane_id"], "w1:p1")
            handled = self.event_action(
                "defer",
                first,
                {"reason": "Waiting for decision", "responsible_party": "operator"},
            )
            self.assertEqual(handled["event"]["handling"], "deferred")
            after_defer = self.context()["observation"]["events"][0]
            for fd in gates.values():
                os.write(fd, b"1")
            _, stderr = child.communicate(timeout=6)
            self.assertEqual(child.returncode, 0, stderr)
            saved = self.context()["observation"]
            self.assertEqual(saved["targets"], targets)
            self.assertEqual(len(saved["events"]), 2)
            self.assertEqual(saved["events"][0], after_defer)
            self.assertEqual(saved["events"][1]["handling"], "pending")
            self.assertTrue(
                all(cursor["reported"] == "needs_input" for cursor in saved["contexts"])
            )
        finally:
            if child.poll() is None:
                child.kill()
            child.communicate(timeout=3)
