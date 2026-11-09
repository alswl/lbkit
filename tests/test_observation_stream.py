"""JSONL streaming must deliver durable events while its listener remains alive."""

import json
import select
import subprocess
import sys

from coordination_helpers import REPO
from observation_fixtures import target
from test_observation_wait import ManagedWaitCase


class ManagedStreamTest(ManagedWaitCase):
    def spawn_stream(self, timeout="2"):
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
                timeout,
                "--expect-version",
                self.context()["version_token"],
                "--json",
            ],
            env=self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )

        def cleanup():
            if child.poll() is None:
                child.kill()
            child.communicate(timeout=3)

        self.addCleanup(cleanup)
        return child

    def test_compact_event_is_flushed_after_commit_before_exit(self):
        self.setup_observation()
        self.runtime([target()], ["blocked"])
        child = self.spawn_stream()
        self.assertTrue(
            select.select([child.stdout], [], [], 3)[0], "no flushed output"
        )
        line = child.stdout.readline()
        self.assertTrue(line, child.stderr.read() if child.poll() is not None else b"")
        event = json.loads(line)
        self.assertEqual(event["type"], "event")
        self.assertIsNone(child.poll())
        saved = self.context()["observation"]
        self.assertIn(event["event_key"], [row["id"] for row in saved["events"]])
        rest, stderr = child.communicate(timeout=4)
        self.assertEqual(child.returncode, 0, stderr)
        rows = [event, *[json.loads(row) for row in rest.splitlines()]]
        self.assertEqual([row["type"] for row in rows], ["event", "listener_end"])
        self.assertEqual(rows[-1]["reason"], "timeout")
        for raw in [line.rstrip(b"\n"), *rest.splitlines()]:
            self.assertEqual(
                raw.decode(), json.dumps(json.loads(raw), separators=(",", ":"))
            )
        self.assertEqual(stderr, b"")

    def test_quiet_interval_has_only_one_lifecycle_line_and_no_heartbeat(self):
        self.setup_observation()
        self.runtime([target()], ["working"])
        child = self.spawn_stream(timeout="0.5")
        stdout, stderr = child.communicate(timeout=3)
        self.assertEqual(child.returncode, 0, stderr)
        rows = [json.loads(row) for row in stdout.splitlines()]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["type"], "listener_end")
        self.assertEqual(rows[0]["reason"], "timeout")
        self.assertEqual(self.context()["observation"]["events"], [])

    def test_broken_pipe_stops_listener_but_preserves_committed_event(self):
        self.setup_observation()
        self.runtime([target()], ["blocked"])
        child = self.spawn_stream(timeout="4")
        child.stdout.close()
        child.stdout = None
        _, stderr = child.communicate(timeout=3)
        # Click uses its existing EPIPE exit convention.
        self.assertEqual(child.returncode, 1, stderr)
        saved = self.context()["observation"]
        self.assertEqual(len(saved["events"]), 1)
        self.assertEqual(saved["events"][0]["observation"]["kind"], "needs_input")
        self.assertEqual(saved["listener"]["status"], "ended")
        # Lock release is demonstrated by another admitted wait, not inferred
        # from the stop receipt or the saved diagnostic status.
        result = self.managed_wait(timeout="0.15")
        self.assertEqual(result["new_events"], [])
        self.assertEqual(len(result["unresolved_events"]), 1)

    def test_partial_delivery_recovers_both_committed_worker_events(self):
        import os
        from unittest.mock import patch

        from click.testing import CliRunner

        from logbook_cli import render
        from logbook_cli.cli import main

        targets = [target(1), target(2)]
        self.setup_observation(targets)
        self.runtime(targets, ["blocked", "blocked"])
        token = self.context()["version_token"]
        emit = render.emit_jsonl
        notified = []

        def fail_second_notification(value):
            if value["type"] == "event":
                if notified:
                    raise BrokenPipeError("injected second notification failure")
                notified.append(value["event_key"])
            emit(value)

        with CliRunner().isolation() as streams:
            with (
                patch.dict(os.environ, self.env),
                patch.object(
                    render, "emit_jsonl", side_effect=fail_second_notification
                ),
            ):
                code = main(
                    [
                        "--root",
                        str(self.root),
                        "agent",
                        "wait",
                        "--log",
                        "log.md",
                        "--stream",
                        "--timeout",
                        "3",
                        "--expect-version",
                        token,
                        "--json",
                    ]
                )
            sys.stdout.flush()
            output = streams[0].getvalue()
        self.assertNotEqual(code, 0)
        rows = [json.loads(line) for line in output.splitlines()]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["event_key"], notified[0])
        saved = self.context()["observation"]
        self.assertEqual(len(saved["events"]), 2)
        self.assertTrue(all(row["handling"] == "pending" for row in saved["events"]))
        self.assertEqual(saved["listener"]["status"], "ended")

    def test_broken_pipe_on_unavailable_worker_stops_before_deadline(self):
        self.setup_observation()
        # No scripted status response: the offline adapter reports unavailable.
        child = self.spawn_stream(timeout="4")
        child.stdout.close()
        child.stdout = None
        try:
            child.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            saved = self.context()["observation"]
            self.assertEqual(saved["events"][0]["observation"]["kind"], "unavailable")
            self.fail(
                "saved unavailable event hit closed stdout but listener kept waiting"
            )
        self.assertEqual(child.returncode, 1)
        self.assertEqual(self.context()["observation"]["listener"]["status"], "ended")

    def test_unavailable_worker_emits_failed_lifecycle_not_a_successful_timeout(self):
        self.setup_observation()
        child = self.spawn_stream()
        stdout, stderr = child.communicate(timeout=3)
        self.assertEqual(child.returncode, 1, stderr)
        rows = [json.loads(row) for row in stdout.splitlines()]
        self.assertEqual([row["type"] for row in rows], ["event", "listener_end"])
        self.assertEqual(rows[0]["kind"], "unavailable")
        self.assertEqual(rows[-1]["reason"], "failed")

    def test_stream_dry_run_returns_preview_without_listener_or_runtime_effects(self):
        self.setup_observation()
        before = self.snapshot()
        token = self.context()["version_token"]
        result = self.run_process(
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
                "--dry-run",
                "--timeout",
                "2",
                "--expect-version",
                token,
                "--json",
            ]
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(
            result.stdout,
            "dry-run must return its preview rather than silently discard it",
        )
        self.assertTrue(json.loads(result.stdout)["dry_run"])
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.calls(), [])
