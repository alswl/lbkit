"""Foundation public contracts; unimplemented behavior stays visibly Red.

Until the command surface exists, failures at context/configure admission do not
prove the later CAS and persistence assertions have been reached.
"""

import json
import sys

from coordination_helpers import REPO
from observation_fixtures import ObservationTest, target


class FoundationCase(ObservationTest):
    def snapshot(self):
        # Include directories and links: even an empty state directory is a write.
        result = {}
        for path in self.root.rglob("*"):
            key = str(path.relative_to(self.root))
            if path.is_symlink():
                result[key] = ("symlink", str(path.readlink()))
            elif path.is_dir():
                result[key] = ("directory",)
            elif path.is_file():
                result[key] = ("file", path.read_bytes())
        return result

    def context(self, log="log.md"):
        return self.cli("agent", "observation", "context", log)

    def observation_files(self):
        return sorted((self.root / "lb" / "observations").glob("*.json"))

    def configure(self, token, *, dry_run=False, code=0):
        return self.cli(
            "agent", "observation", "configure", "log.md",
            "--input-file", "targets.json", "--expect-version", token,
            *(("--dry-run",) if dry_run else ()), code=code,
        )

    def assert_refusal(self, result, category):
        # A Click unknown-command/option error must never pass a refusal test.
        self.assertEqual(result.returncode, 4, result.stdout + result.stderr)
        self.assertIn(category, result.stdout + result.stderr)

    def prepared(self):
        self.identify()
        self.configuration()
        return self.context()["version_token"]



class ObservationFoundationTest(FoundationCase):
    def test_absent_context_returns_token_without_writing(self):
        self.identify()
        before = self.snapshot()
        result = self.context()
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(len(result["version_token"]), 64)
        self.assertGreaterEqual(int(result["version_token"], 16), 0)
        self.assertEqual(self.observation_files(), [])
        self.assertEqual(self.calls(), [])

    def test_repeated_absent_context_has_stable_token_and_no_writes(self):
        self.identify()
        before = self.snapshot()
        first = self.context()
        second = self.context()
        self.assertEqual(first["version_token"], second["version_token"])
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.calls(), [])

    def test_absent_tokens_are_scoped_to_document_identity(self):
        self.identify()
        first = self.context()["version_token"]
        other = self.root / "other.md"
        other.write_text("# Another log\n\n## Stage 01 Build\n\n- [ ] Another task\n")
        token = self.cli("log", "context", "other.md")["version_token"]
        self.cli(
            "task", "identify", "other.md", "--stage", "Stage 01 Build",
            "--task", "Another task", "--task-id", "T2", "--expect-version", token,
        )
        self.assertNotEqual(first, self.context("other.md")["version_token"])
        self.assertEqual(first, self.context()["version_token"])

    def test_configure_surface_requires_input_and_token(self):
        # Independently reaches configure: not blocked behind a context setup call.
        result = self.run_process([
            sys.executable, str(REPO / "bin/lb"), "--root", str(self.root),
            "agent", "observation", "configure", "--help",
        ])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("--input-file", result.stdout)
        self.assertIn("--expect-version", result.stdout)
        self.assertIn("--dry-run", result.stdout)
        for flags, missing in (([], "--input-file"),
                               (["--input-file", "targets.json"], "--expect-version")):
            with self.subTest(missing=missing):
                result = self.cli("agent", "observation", "configure", "log.md", *flags, code=2)
                self.assertIn(f"Missing option '{missing}'", result.stderr)

    def test_missing_identity_refuses_without_implicit_migration(self):
        # Deliberately no identify/migrate; use the context-issued token only.
        self.configuration()
        token = self.context()["version_token"]
        before = self.snapshot()
        result = self.configure(token, code=4)
        self.assert_refusal(result, "identity_missing")
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.observation_files(), [])
        self.assertEqual(self.calls(), [])

    def test_absent_token_initializes_one_durable_observation(self):
        token = self.prepared()
        log = self.log.read_bytes()
        document_state = (self.root / "lb" / "log.md.json").read_bytes()
        result = self.configure(token)
        files = self.observation_files()
        self.assertEqual(len(files), 1)
        json.loads(files[0].read_bytes())
        self.assertNotEqual(token, result["version_token"])
        self.assertEqual(self.context()["version_token"], result["version_token"])
        self.assertEqual(self.log.read_bytes(), log)
        self.assertEqual((self.root / "lb" / "log.md.json").read_bytes(), document_state)
        self.assertEqual(self.calls(), [])

    def test_stale_absent_token_cannot_replace_configuration(self):
        old = self.prepared()
        self.configure(old)
        self.configuration([target(2)])
        before = self.snapshot()
        result = self.configure(old, code=4)
        self.assert_refusal(result, "version_conflict")
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.calls(), [])

    def test_identical_request_with_stale_token_refuses_before_replay(self):
        old = self.prepared()
        self.configure(old)
        before = self.snapshot()
        result = self.configure(old, code=4)
        self.assert_refusal(result, "version_conflict")
        self.assertEqual(self.snapshot(), before)

    def test_document_token_is_not_observation_write_authority(self):
        self.prepared()
        token = self.cli("log", "context", "log.md")["version_token"]
        before = self.snapshot()
        result = self.configure(token, code=4)
        self.assert_refusal(result, "version_conflict")
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.calls(), [])

    def test_initial_dry_run_creates_no_files_and_does_not_reserve(self):
        token = self.prepared()
        before = self.snapshot()
        self.configure(token, dry_run=True)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.context()["version_token"], token)
        self.assertEqual(self.observation_files(), [])
        self.assertEqual(self.calls(), [])
        self.configure(token)
        self.assertEqual(len(self.observation_files()), 1)

    def test_existing_configuration_dry_run_preserves_state_and_token(self):
        token = self.prepared()
        self.configure(token)
        fresh = self.context()["version_token"]
        self.configuration([target(2)])
        before = self.snapshot()
        self.configure(fresh, dry_run=True)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.context()["version_token"], fresh)
        self.assertEqual(self.calls(), [])

    def test_dry_run_still_refuses_stale_token(self):
        old = self.prepared()
        self.configure(old)
        before = self.snapshot()
        result = self.configure(old, dry_run=True, code=4)
        self.assert_refusal(result, "version_conflict")
        self.assertEqual(self.snapshot(), before)


class RequiredInputCompatibilityTest(ObservationTest):
    def test_unrelated_commands_keep_required_input_validation(self):
        before = self.snapshot()
        for command in ("open", "close-session"):
            with self.subTest(command=command):
                result = self.cli("agent", command, code=2)
                self.assertIn("Missing option '--input-file'", result.stderr)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.calls(), [])
