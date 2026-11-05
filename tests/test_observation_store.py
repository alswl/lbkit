"""Filesystem contracts exercised through the CLI, with no new module imports.

OS fault injection is limited to Observation files. Command-admission failures
are surface Red only; these tests must be rerun through their storage assertions.
"""

import fcntl
import json
import os
import stat
import sys
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner
from observation_fixtures import target
from test_observation_cli import FoundationCase

from logbook_cli.cli import main


class ObservationStorageTest(FoundationCase):
    def existing(self):
        token = self.prepared()
        self.configure(token)
        return self.observation_files()[0], self.context()["version_token"]

    def invoke_configure(self, token):
        # main supplies the same error-to-exit mapping as the subprocess launcher.
        with CliRunner().isolation() as streams:
            code = main(
                [
                    "--root",
                    str(self.root),
                    "agent",
                    "observation",
                    "configure",
                    "log.md",
                    "--input-file",
                    "targets.json",
                    "--expect-version",
                    token,
                    "--json",
                ]
            )
            output = streams[0].getvalue()
        return code, output

    def test_symlink_observation_directory_cannot_escape_repository(self):
        token = self.prepared()
        outside = self.base / "outside"
        outside.mkdir()
        sentinel = outside / "sentinel"
        sentinel.write_text("untouched")
        directory = self.root / "lb" / "observations"
        directory.symlink_to(outside, target_is_directory=True)
        before = self.snapshot()
        result = self.configure(token, code=4)
        self.assertEqual(result.returncode, 4)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(list(outside.iterdir()), [sentinel])
        self.assertEqual(sentinel.read_text(), "untouched")

    def test_symlink_state_file_is_not_followed_for_read_or_write(self):
        path, token = self.existing()
        outside = self.base / "external.json"
        saved = path.read_bytes()
        outside.write_bytes(saved)
        path.unlink()
        path.symlink_to(outside)
        self.configuration([target(2)])
        result = self.cli("agent", "observation", "context", "log.md", code=4)
        self.assertEqual(result.returncode, 4)
        self.configure(token, code=4)
        self.assertTrue(path.is_symlink())
        self.assertEqual(outside.read_bytes(), saved)

    def test_unknown_format_refuses_without_repair_or_overwrite(self):
        path, token = self.existing()
        value = json.loads(path.read_bytes())
        value["format"] = "unsupported-example-format"
        path.write_text(json.dumps(value))
        before = self.snapshot()
        self.cli("agent", "observation", "context", "log.md", code=4)
        self.configure(token, code=4)
        self.assertEqual(self.snapshot(), before)

    def test_failed_replace_preserves_previous_complete_state(self):
        path, token = self.existing()
        self.configuration([target(2)])
        saved = path.read_bytes()
        replace = os.replace

        def fail_observation_replace(source, destination, *args, **kwargs):
            if Path(destination).name == path.name:
                # At the replacement boundary the old state remains fully readable.
                self.assertEqual(path.read_bytes(), saved)
                if "src_dir_fd" in kwargs:
                    fd = os.open(source, os.O_RDONLY, dir_fd=kwargs["src_dir_fd"])
                    with os.fdopen(fd, "rb") as handle:
                        json.loads(handle.read())
                else:
                    json.loads(Path(source).read_bytes())
                raise OSError("injected replacement failure")
            return replace(source, destination, *args, **kwargs)

        with patch("os.replace", side_effect=fail_observation_replace):
            code, _ = self.invoke_configure(token)
        self.assertNotEqual(code, 0)
        self.assertEqual(path.read_bytes(), saved)
        self.assertEqual(self.context()["version_token"], token)

    def test_directory_fsync_failure_after_replace_requires_reread(self):
        path, token = self.existing()
        self.configuration([target(2)])
        saved = path.read_bytes()
        fsync = os.fsync

        def fail_directory_fsync(fd):
            descriptor = os.fstat(fd)
            directory = path.parent.stat()
            if stat.S_ISDIR(descriptor.st_mode) and (
                descriptor.st_dev,
                descriptor.st_ino,
            ) == (directory.st_dev, directory.st_ino):
                # Replacement occurred, but durable directory persistence failed.
                self.assertNotEqual(path.read_bytes(), saved)
                json.loads(path.read_bytes())
                raise OSError("injected directory fsync failure")
            return fsync(fd)

        with patch("os.fsync", side_effect=fail_directory_fsync):
            code, _ = self.invoke_configure(token)
        self.assertNotEqual(code, 0)
        self.assertNotEqual(path.read_bytes(), saved)
        json.loads(path.read_bytes())
        self.assertNotEqual(self.context()["version_token"], token)
        before = self.snapshot()
        self.assert_refusal(self.configure(token, code=4), "version_conflict")
        self.assertEqual(self.snapshot(), before)

    def test_configure_refuses_while_cooperating_state_writer_holds_lock(self):
        path, token = self.existing()
        self.configuration([target(2)])
        before = self.snapshot()
        fd = os.open(self.root, os.O_RDONLY)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = self.configure(token, code=4)
            self.assertIn("writer_busy", result.stderr)
        finally:
            os.close(fd)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.context()["version_token"], token)

    def test_dry_run_refuses_busy_writer_without_creating_files(self):
        token = self.prepared()
        before = self.snapshot()
        fd = os.open(self.root, os.O_RDONLY)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = self.configure(token, dry_run=True, code=4)
            self.assertIn("writer_busy", result.stderr)
        finally:
            os.close(fd)
        self.assertEqual(self.snapshot(), before)

    def test_concurrent_configure_has_only_one_winner(self):
        # Both subprocesses wait on the same explicit start barrier. Assertions
        # check final durable state and outcomes, not guessed scheduling delays.
        import subprocess
        import sys

        from coordination_helpers import REPO

        _, token = self.existing()
        self.configuration([target(2)])
        other = self.root / "other-targets.json"
        other.write_text(json.dumps({"targets": [target(3)]}))
        import select
        import time

        read_fd, write_fd = os.pipe()
        ready_read, ready_write = os.pipe()
        release_read, release_write = os.pipe()
        children = []
        launch = """import os,sys,runpy
os.read(int(sys.argv[1]),1)
ready, release = int(sys.argv[2]), int(sys.argv[3])
original_open = os.open
first = True
def synchronized_open(name, flags, *args, **kwargs):
    global first
    if first and '.action-' in str(name):
        first = False
        os.write(ready,b'1')
        os.read(release,1)
    return original_open(name,flags,*args,**kwargs)
os.open = synchronized_open
sys.argv = sys.argv[4:]
from pathlib import Path
sys.path.insert(0,str(Path(sys.argv[0]).resolve().parents[1]/'src'))
from logbook_cli.cli import main
raise SystemExit(main(sys.argv[1:]))
"""
        try:
            for input_file in ("targets.json", "other-targets.json"):
                child = subprocess.Popen(
                    [
                        sys.executable,
                        "-c",
                        launch,
                        str(read_fd),
                        str(ready_write),
                        str(release_read),
                        str(REPO / "bin/lb"),
                        "--root",
                        str(self.root),
                        "agent",
                        "observation",
                        "configure",
                        "log.md",
                        "--input-file",
                        input_file,
                        "--expect-version",
                        token,
                        "--json",
                    ],
                    env=self.env,
                    pass_fds=(read_fd, ready_write, release_read),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                children.append(child)
            os.write(write_fd, b"11")
            deadline = time.monotonic() + 4
            ready = 0
            while ready < 2:
                self.assertTrue(
                    select.select(
                        [ready_read], [], [], max(0, deadline - time.monotonic())
                    )[0],
                    "both writers must reach action-lock admission",
                )
                ready += len(os.read(ready_read, 2 - ready))
            os.write(release_write, b"11")
            outputs = [child.communicate(timeout=5) for child in children]
            self.assertEqual(
                sorted(child.returncode for child in children), [0, 4], outputs
            )
            for child, (_, stderr) in zip(children, outputs):
                if child.returncode:
                    self.assertTrue(
                        any(
                            category in stderr
                            for category in (
                                b"version_conflict",
                                b"writer_busy",
                                b"listener_busy",
                                b"delivery_unresolved",
                            )
                        ),
                        stderr,
                    )
            files = self.observation_files()
            self.assertEqual(len(files), 1)
            saved = json.loads(files[0].read_bytes())
            self.assertIn(saved["targets"], ([target(2)], [target(3)]))
            self.assertEqual(self.calls(), [])
        finally:
            for fd in (
                read_fd,
                write_fd,
                ready_read,
                ready_write,
                release_read,
                release_write,
            ):
                os.close(fd)
            for child in children:
                if child.poll() is None:
                    child.kill()
                child.communicate(timeout=2)

    def test_malformed_state_envelope_is_not_exposed_or_repaired(self):
        path, token = self.existing()
        valid = json.loads(path.read_bytes())
        for field, invalid in (
            ("id", None),
            ("targets", []),
            ("contexts", []),
            ("events", "not-a-list"),
            ("answers", {}),
        ):
            with self.subTest(field=field):
                path.write_text(json.dumps({**valid, field: invalid}))
                before = self.snapshot()
                self.cli("agent", "observation", "context", "log.md", code=4)
                self.configure(token, code=4)
                self.assertEqual(self.snapshot(), before)

    def test_parent_swap_does_not_read_replacement_symlink_target(self):
        path, _ = self.existing()
        saved = json.loads(path.read_bytes())
        outside = self.base / "replacement"
        outside.mkdir()
        (outside / path.name).write_text(json.dumps({**saved, "id": "f" * 32}))
        moved = path.parent.with_name("retired-observations")
        opened = os.open
        swapped = False

        def swap_before_open(name, flags, *args, **kwargs):
            nonlocal swapped
            if not swapped and Path(name).name == path.name:
                swapped = True
                path.parent.rename(moved)
                path.parent.symlink_to(outside, target_is_directory=True)
            return opened(name, flags, *args, **kwargs)

        with patch("os.open", side_effect=swap_before_open):
            with CliRunner().isolation() as streams:
                code = main(
                    [
                        "--root",
                        str(self.root),
                        "agent",
                        "observation",
                        "context",
                        "log.md",
                        "--json",
                    ]
                )
                sys.stdout.flush()
                output = streams[0].getvalue()
        self.assertTrue(swapped)
        if code == 0:
            self.assertEqual(json.loads(output)["observation"], saved)
        else:
            self.assertEqual(code, 4)


class ObservationCapacityTest(FoundationCase):
    def existing(self):
        self.configure(self.prepared())
        return self.observation_files()[0]

    def test_event_answer_and_history_counts_refuse_without_eviction(self):
        from logbook_cli import observation
        from logbook_cli.document import LbError

        path = self.existing()
        original = json.loads(path.read_bytes())
        for field, items in (
            ("events", [{"id": str(i), "handling": "resolved"} for i in range(4097)]),
            ("answers", [{"id": str(i), "status": "confirmed"} for i in range(4097)]),
            (
                "events",
                [
                    {
                        "id": "event",
                        "handling": "resolved",
                        "history": [{"id": str(i)} for i in range(8193)],
                    }
                ],
            ),
        ):
            with self.subTest(field=field, count=len(items)):
                value = {**original, field: items}
                before = json.dumps(value, sort_keys=True)
                with self.assertRaisesRegex(LbError, "capacity_exceeded"):
                    observation.admit(value)
                self.assertEqual(json.dumps(value, sort_keys=True), before)

    def test_encoded_state_limit_uses_bytes_not_character_count(self):
        from logbook_cli import observation
        from logbook_cli.document import LbError

        value = {
            "targets": [],
            "events": [],
            "answers": [],
            "padding": "界" * (3 * 1024 * 1024),
        }
        with self.assertRaisesRegex(LbError, "capacity_exceeded"):
            observation.admit(value)

    def test_pending_work_keeps_completion_space_that_resolved_work_releases(self):
        from logbook_cli import observation
        from logbook_cli.document import LbError

        value = json.loads(self.existing().read_bytes())
        value["events"] = [{"id": "event", "handling": "pending", "history": []}]
        value["answers"] = [{"id": "answer", "status": "unknown", "history": []}]
        # This limit fits current bytes but not the maximum completion records.
        with patch.object(observation, "STATE_LIMIT", 160 * 1024, create=True):
            with self.assertRaisesRegex(LbError, "capacity_exceeded"):
                observation.admit(value)
            value["events"][0]["handling"] = "resolved"
            value["answers"][0]["status"] = "confirmed"
            observation.admit(value)

    def test_next_target_batch_and_its_terminal_history_slots_are_reserved(self):
        from logbook_cli import observation
        from logbook_cli.document import LbError

        value = json.loads(self.existing().read_bytes())
        value["events"] = [{"id": str(i), "handling": "resolved"} for i in range(4096)]
        with self.assertRaisesRegex(LbError, "capacity_exceeded"):
            observation.admit(value)
        value["events"] = [
            {
                "id": "event",
                "handling": "pending",
                "history": [{"id": str(i)} for i in range(8191)],
            }
        ]
        with self.assertRaisesRegex(LbError, "capacity_exceeded"):
            observation.admit(value)

    def test_configure_applies_admission_under_writer_lock_without_changing_saved_work(
        self,
    ):
        path = self.existing()
        value = json.loads(path.read_bytes())
        value["events"] = [{"id": str(i), "handling": "resolved"} for i in range(4096)]
        path.write_text(json.dumps(value))
        token = self.context()["version_token"]
        before = self.snapshot()
        result = self.configure(token, code=4)
        self.assertIn("capacity_exceeded", result.stderr)
        self.assertEqual(self.snapshot(), before)

    def test_completion_payload_bounds_cover_summary_reference_and_history_records(
        self,
    ):
        from logbook_cli import observation
        from logbook_cli.document import LbError

        original = json.loads(self.existing().read_bytes())
        for conclusion in (
            {"summary": "界" * 1366},
            {"evidence": ["r" * 2049]},
            {"evidence": ["https://example.com/evidence"] * 5},
        ):
            with self.subTest(conclusion=next(iter(conclusion))):
                value = {
                    **original,
                    "events": [
                        {
                            "id": "event",
                            "handling": "resolved",
                            "conclusion": conclusion,
                        }
                    ],
                }
                with self.assertRaisesRegex(LbError, "capacity_exceeded"):
                    observation.admit(value)
        value = {
            **original,
            "answers": [
                {
                    "id": "answer",
                    "status": "confirmed",
                    "history": [{"padding": "x" * (16 * 1024)}],
                }
            ],
        }
        with self.assertRaisesRegex(LbError, "capacity_exceeded"):
            observation.admit(value)

    def test_terminal_work_can_use_its_reservation_when_new_batch_cannot_fit(self):
        from logbook_cli import observation
        from logbook_cli.document import LbError

        value = json.loads(self.existing().read_bytes())
        value["events"] = [
            {"id": "first", "handling": "pending", "history": []},
            {"id": "second", "handling": "pending", "history": []},
        ]
        with patch.object(observation, "STATE_LIMIT", 140 * 1024):
            with self.assertRaisesRegex(LbError, "capacity_exceeded"):
                observation.admit(value)
            observation.admit(value, new_work=False)
            value["events"][0].update(
                handling="resolved",
                conclusion={"summary": "x" * 4096},
                history=[{"id": "resolved", "evidence": ["r" * 2048] * 4}],
            )
            observation.admit(value, new_work=False)
            self.assertEqual(
                value["events"][1],
                {"id": "second", "handling": "pending", "history": []},
            )

    def test_repeated_deferral_cannot_spend_another_events_completion_reserve(self):
        from logbook_cli import observation
        from logbook_cli.document import LbError

        value = json.loads(self.existing().read_bytes())
        value["events"] = [
            {"id": "first", "handling": "deferred", "history": []},
            {"id": "second", "handling": "pending", "history": []},
        ]
        with patch.object(observation, "STATE_LIMIT", 140 * 1024):
            observation.admit(value, new_work=False)
            value["events"][0]["history"] = [{"summary": "x" * 4096} for _ in range(4)]
            with self.assertRaisesRegex(LbError, "capacity_exceeded"):
                observation.admit(value, new_work=False)
            self.assertEqual(value["events"][1]["handling"], "pending")

    def test_configure_checks_capacity_while_holding_the_actual_writer_lock(self):
        from logbook_cli import observation
        from logbook_cli.services.agent_observation import configure

        token = self.prepared()
        admission = observation.admit
        seen = []

        def verify_locked(value, **kwargs):
            fd = os.open(self.root, os.O_RDONLY)
            try:
                with self.assertRaises(BlockingIOError):
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                seen.append(True)
            finally:
                os.close(fd)
            return admission(value, **kwargs)

        with patch.object(observation, "admit", side_effect=verify_locked):
            configure(str(self.root), "log.md", "targets.json", token, False)
        self.assertEqual(seen, [True])
        self.assertEqual(len(self.observation_files()), 1)
