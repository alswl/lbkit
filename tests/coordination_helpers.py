"""Disposable repositories and bounded real-entry calls for coordination tests."""

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FIXTURES = REPO / "tests/fixtures/coordination"


class CoordinationTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="lbkit-case-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root = self.base / "repo"
        self.root.mkdir()
        self.log = self.root / "log.md"
        self.log.write_text("# Example\n\n## Stage 01 Build\n\n- [ ] Correct typo\n")
        self.fake = self.base / "fake"
        self.fake.mkdir()
        bin_dir = self.base / "bin"
        bin_dir.mkdir()
        shutil.copy2(REPO / "tests/fixtures/herdr_fake.py", bin_dir / "herdr")
        self.env = {
            **os.environ,
            "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
            "HERDR_ENV": "1",
            "HERDR_FAKE_DIR": str(self.fake),
        }
        self.script([])

    def script(self, rules):
        (self.fake / "script.json").write_text(json.dumps({"rules": rules}))
        (self.fake / "counters.json").unlink(missing_ok=True)

    def fixture(self, name):
        self.log.write_bytes((FIXTURES / name).read_bytes())

    def snapshot(self):
        return {
            str(p.relative_to(self.root)): p.read_bytes()
            for p in self.root.rglob("*")
            if p.is_file() and p.name != ".lock"
        }

    def run_process(self, args, timeout=10):
        process = subprocess.Popen(
            args,
            cwd=self.root,
            env=self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.communicate(timeout=1)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.communicate(timeout=1)
            raise
        return subprocess.CompletedProcess(args, process.returncode, stdout, stderr)

    def cli(self, *args, code=0, timeout=10):
        result = self.run_process(
            [
                sys.executable,
                str(REPO / "bin/lb"),
                "--root",
                str(self.root),
                *args,
                "--json",
            ],
            timeout,
        )
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return json.loads(result.stdout) if code == 0 else result

    def context(self):
        return self.cli("log", "context", "log.md")

    def token(self):
        return self.context()["version_token"]

    def identify(self, text="Correct typo", identity="T1"):
        return self.cli(
            "task",
            "identify",
            "log.md",
            "--stage",
            "Stage 01 Build",
            "--task",
            text,
            "--task-id",
            identity,
            "--expect-version",
            self.token(),
        )

    def action(self, action, identity="T1", *args, code=0, token=None):
        return self.cli(
            "task",
            action,
            "log.md",
            identity,
            "--basis",
            "Authorized work",
            "--expect-version",
            token or self.token(),
            *args,
            code=code,
        )

    def show(self, identity="T1"):
        return self.cli("task", "show", "log.md", identity)["task"]

    def calls(self):
        path = self.fake / "calls.jsonl"
        return (
            [json.loads(s) for s in path.read_text().splitlines()]
            if path.exists()
            else []
        )
