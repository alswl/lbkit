"""Managed one-shot wait contracts against isolated offline workers."""

import fcntl
import json
import os

import test_agent_wait_e2e as raw_wait
from observation_fixtures import target
from test_observation_cli import FoundationCase


class ManagedWaitCase(FoundationCase):
    runtime = raw_wait.AgentWaitE2ETest.runtime

    def setup_observation(self, targets=None):
        self.identify()
        self.configuration(targets)
        self.configure(self.context()["version_token"])

    def managed_wait(self, *, timeout="1", code=0, token=None, extra=()):
        return self.cli(
            "agent",
            "wait",
            "--log",
            "log.md",
            "--timeout",
            timeout,
            "--expect-version",
            token or self.context()["version_token"],
            *extra,
            code=code,
            timeout=5,
        )


class ManagedWaitTest(ManagedWaitCase):
    def test_absent_configuration_refuses_without_writes_or_runtime_calls(self):
        self.identify()
        before = self.snapshot()
        result = self.managed_wait(code=4)
        self.assertIn("observation_not_configured", result.stderr)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.calls(), [])

    def test_stale_authority_refuses_before_runtime_or_listener_creation(self):
        self.setup_observation()
        before = self.snapshot()
        result = self.managed_wait(token="0" * 64, code=4)
        self.assertIn("version_conflict", result.stderr)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.calls(), [])

    def test_managed_input_file_is_forbidden(self):
        self.setup_observation()
        before = self.snapshot()
        result = self.managed_wait(extra=("--input-file", "targets.json"), code=2)
        self.assertIn("--input-file", result.stderr)
        self.assertIn("managed", result.stderr)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.calls(), [])

    def test_event_and_cursor_are_durable_without_task_completion(self):
        self.setup_observation()
        self.runtime([target()], ["blocked"])
        log = self.log.read_bytes()
        document = (self.root / "lb" / "log.md.json").read_bytes()
        result = self.managed_wait()
        self.assertEqual(result["reason"], "change")
        self.assertEqual(len(result["new_events"]), 1)
        event = result["new_events"][0]
        self.assertEqual(event["observation"]["kind"], "needs_input")
        saved = self.context()["observation"]
        self.assertIn(event, saved["events"])
        self.assertEqual(saved["contexts"][0]["reported"], "needs_input")
        self.assertEqual(saved["listener"]["status"], "ended")
        self.assertEqual(self.log.read_bytes(), log)
        self.assertEqual((self.root / "lb" / "log.md.json").read_bytes(), document)
        again = self.managed_wait(timeout="0.15")
        self.assertEqual(again["reason"], "timeout")
        self.assertEqual(again["new_events"], [])
        self.assertEqual(again["unresolved_events"], [event])

    def test_working_rearm_is_persisted_without_a_notification(self):
        item = target()
        item["baseline"]["state"] = "idle"
        self.setup_observation([item])
        self.runtime([item], ["working"])
        self.assertEqual(self.managed_wait()["new_events"], [])
        self.assertTrue(self.context()["observation"]["contexts"][0]["armed"])
        self.runtime([item], ["idle"])
        result = self.managed_wait()
        self.assertEqual(result["new_events"][0]["observation"]["kind"], "settled")

    def test_two_workers_keep_all_targets_and_event_history_across_calls(self):
        targets = [target(1), target(2)]
        self.setup_observation(targets)
        self.runtime(targets, ["blocked", "blocked"])
        seen = set()
        for _ in range(2):
            result = self.managed_wait()
            seen.update(
                event["observation"]["binding"]["pane_id"]
                for event in result["new_events"]
            )
        self.assertEqual(seen, {"w1:p1", "w1:p2"})
        saved = self.context()["observation"]
        self.assertEqual(saved["targets"], targets)
        self.assertEqual(len(saved["events"]), 2)

    def test_duplicate_listener_and_configure_refuse_without_worker_calls(self):
        self.setup_observation()
        state_path = self.observation_files()[0]
        lock_path = state_path.with_suffix(".listener")
        fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            before = self.snapshot()
            result = self.managed_wait(code=4)
            self.assertIn("listener_busy", result.stderr)
            result = self.configure(self.context()["version_token"], code=4)
            self.assertIn("listener_busy", result.stderr)
            self.assertEqual(self.snapshot(), before)
        finally:
            os.close(fd)
        self.assertEqual(self.calls(), [])
        json.loads(state_path.read_bytes())

    def test_event_and_cursor_commit_in_one_replace_before_any_stdout(self):
        import sys
        from pathlib import Path
        from unittest.mock import patch

        from click.testing import CliRunner

        from logbook_cli.cli import main

        self.setup_observation()
        self.runtime([target()], ["blocked"])
        token = self.context()["version_token"]
        path = self.observation_files()[0]
        replace = os.replace
        checked = []
        with CliRunner().isolation() as streams:

            def verify_replace(source, destination, **kwargs):
                if Path(destination).name == path.name:
                    fd = os.open(source, os.O_RDONLY, dir_fd=kwargs["src_dir_fd"])
                    with os.fdopen(fd, "rb") as handle:
                        candidate = json.loads(handle.read())
                    old = json.loads(path.read_bytes())
                    if candidate["events"] and not old["events"]:
                        self.assertEqual(
                            candidate["contexts"][0]["reported"], "needs_input"
                        )
                        self.assertEqual(
                            candidate["events"][0]["observation"]["kind"], "needs_input"
                        )
                        sys.stdout.flush()
                        self.assertEqual(streams[0].getvalue(), b"")
                        checked.append(True)
                return replace(source, destination, **kwargs)

            with (
                patch.dict(os.environ, self.env),
                patch("os.replace", side_effect=verify_replace),
            ):
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
        self.assertEqual(code, 0)
        self.assertEqual(checked, [True])
        self.assertEqual(len(json.loads(output)["new_events"]), 1)

    def test_working_rearm_is_saved_before_wait_process_returns(self):
        import signal
        import subprocess
        import sys

        from coordination_helpers import REPO

        item = target()
        item["baseline"]["state"] = "idle"
        self.setup_observation([item])
        self.runtime([item], ["working"])
        self.barrier("native-wait")
        script = json.loads((self.fake / "script.json").read_text())
        for rule in script["rules"]:
            if rule["argv"] == ["agent", "wait"]:
                rule["responses"][0]["barriers"] = {"before_receipt": "native-wait"}
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
                "--timeout",
                "4",
                "--expect-version",
                self.context()["version_token"],
                "--json",
            ],
            env=self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            self.wait_checkpoint("before_receipt")
            self.assertIsNone(child.poll())
            saved = self.context()["observation"]
            self.assertTrue(saved["contexts"][0]["armed"])
            self.assertEqual(saved["events"], [])
            child.send_signal(signal.SIGINT)
            child.communicate(timeout=3)
            self.assertEqual(child.returncode, 130)
        finally:
            if child.poll() is None:
                child.kill()
            child.communicate(timeout=3)
