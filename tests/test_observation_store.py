"""Filesystem contracts exercised through the CLI, with no new module imports.

OS fault injection is limited to Observation files. Command-admission failures
are surface Red only; these tests must be rerun through their storage assertions.
"""

import json
import os
import stat
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
            code = main([
                "--root", str(self.root), "agent", "observation", "configure",
                "log.md", "--input-file", "targets.json", "--expect-version", token,
                "--json",
            ])
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
            if Path(destination) == path:
                # At the replacement boundary the old state remains fully readable.
                self.assertEqual(path.read_bytes(), saved)
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
            if (stat.S_ISDIR(descriptor.st_mode)
                    and (descriptor.st_dev, descriptor.st_ino)
                    == (directory.st_dev, directory.st_ino)):
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

