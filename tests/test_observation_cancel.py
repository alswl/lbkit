"""Owned native wait cancellation and abandoned-invocation recovery."""

import json
import os
import signal
import time

import test_observation_stream as stream_fixture
from observation_fixtures import target
from test_observation_wait import ManagedWaitCase


class ManagedCancelTest(ManagedWaitCase):
    spawn_stream = stream_fixture.ManagedStreamTest.spawn_stream

    def held_native_wait(self):
        self.setup_observation()
        self.runtime([target()], ["working"])
        self.barrier("held-wait")
        script = json.loads((self.fake / "script.json").read_text())
        for rule in script["rules"]:
            if rule["argv"] == ["agent", "wait"]:
                rule["responses"][0].update(
                    barriers={"before_receipt": "held-wait"}, ignore_term=True
                )
        self.script(script["rules"])
        child = self.spawn_stream(timeout="8")
        self.addCleanup(self.reclaim_fixture_children)
        self.wait_checkpoint("before_receipt")
        return child

    def reclaim_fixture_children(self):
        for row in self.calls():
            if row["kind"] == "start":
                try:
                    os.kill(row["pid"], signal.SIGKILL)
                except ProcessLookupError:
                    pass

    def test_repeated_sigterm_cleans_owned_children_and_releases_listener(self):
        child = self.held_native_wait()
        child.send_signal(signal.SIGTERM)
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and child.poll() is None:
            if any(row["kind"] == "signal" for row in self.calls()):
                child.send_signal(signal.SIGTERM)
                break
            time.sleep(0.005)
        stdout, stderr = child.communicate(timeout=3)
        self.assertEqual(child.returncode, 143, stderr)
        rows = [json.loads(line) for line in stdout.splitlines()]
        self.assertEqual(rows[-1]["reason"], "cancelled")
        self.assertEqual(self.context()["observation"]["listener"]["status"], "ended")
        for row in self.calls():
            if row["kind"] == "start":
                with self.assertRaises(ProcessLookupError):
                    os.kill(row["pid"], 0)
        self.assertEqual(self.managed_wait(timeout="0.2")["new_events"], [])

    def test_hard_kill_recovers_abandoned_gap_without_trusting_saved_pid(self):
        child = self.held_native_wait()
        child.kill()
        child.communicate(timeout=2)
        self.assertEqual(child.returncode, -9)
        self.reclaim_fixture_children()
        before = self.context()["observation"]
        self.assertEqual(before["listener"]["status"], "active")
        self.runtime([target()], ["working"])
        result = self.managed_wait(timeout="0.3")
        self.assertTrue(
            any(
                row["observation"]["kind"] == "observation_gap"
                for row in result["new_events"]
            )
        )
        self.assertEqual(self.context()["observation"]["listener"]["status"], "ended")

    def test_stale_active_record_and_reused_pid_are_not_listener_ownership(self):
        self.setup_observation()
        path = self.observation_files()[0]
        value = json.loads(path.read_bytes())
        value["listener"] = {
            "status": "active",
            "invocation_id": "prior-example",
            "pid": os.getpid(),
        }
        path.write_text(json.dumps(value))
        self.runtime([target()], ["working"])
        result = self.managed_wait(timeout="0.3")
        self.assertEqual(len(result["new_events"]), 1)
        self.assertEqual(
            result["new_events"][0]["observation"]["kind"], "observation_gap"
        )
        self.assertNotEqual(result["invocation_id"], "prior-example")
