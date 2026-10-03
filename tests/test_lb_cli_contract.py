"""Black-box contracts for the existing argparse CLI; no real project writes."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CLI = Path(__file__).resolve().parents[1] / "scripts" / "lb.py"
BIN = Path(__file__).resolve().parents[1] / "bin" / "lb"


class CliContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.log = self.root / "log.md"
        self.log.write_text(
            "# Demo\n\n## 🛫 Stage 01 Build\n\n- [ ] 开发：示例\n", encoding="utf-8"
        )

    def run_cli(
        self, *args: str, cwd: Path | None = None
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CLI), *args],
            cwd=cwd if cwd is not None else self.root,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )

    def test_help_needs_no_existing_root(self):
        for command in ((), ("context",), ("task", "update")):
            with self.subTest(command=command):
                result = self.run_cli("--root", "missing", *command, "--help")
                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stderr, "")
                self.assertIn("--root", result.stdout)
                self.assertIn("--help", result.stdout)

    def test_root_supported_at_each_command_level(self):
        for args in (
            ("--root", str(self.root), "context", "log.md", "--json"),
            ("context", "log.md", "--root", str(self.root), "--json"),
            ("context", "log.md", f"--root={self.root}", "--json"),
        ):
            with self.subTest(args=args):
                result = self.run_cli(*args, cwd=self.root.parent)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, "")
                self.assertEqual(json.loads(result.stdout)["path"], "log.md")

    def test_executable_bin_entrypoint_from_other_directory(self):
        result = subprocess.run(
            [str(BIN), "context", "log.md", "--root", str(self.root), "--json"],
            cwd=self.root.parent,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["path"], "log.md")

    def test_end_of_options_preserves_root_named_file(self):
        (self.root / "--root").write_bytes(self.log.read_bytes())
        result = self.run_cli("context", "--json", "--", "--root")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["path"], "--root")

    def test_expected_errors_leave_stdout_empty(self):
        for args, code in (
            (("unknown",), 2),
            (("check", "--json"), 2),
            (("context", "missing.md", "--json"), 3),
            (("--root", str(self.log), "list", "--json"), 3),
        ):
            with self.subTest(args=args):
                result = self.run_cli(*args)
                self.assertEqual(result.returncode, code)
                self.assertEqual(result.stdout, "")
                self.assertTrue(result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    def test_nested_root_and_dry_run_do_not_write(self):
        before = self.log.read_bytes()
        context = self.run_cli("context", "log.md", "--json")
        token = json.loads(context.stdout)["version_token"]
        for prefix in (
            ("--root", str(self.root), "task", "update"),
            ("task", "--root", str(self.root), "update"),
            ("task", "update", "--root", str(self.root)),
        ):
            with self.subTest(prefix=prefix):
                result = self.run_cli(
                    *prefix,
                    "log.md",
                    "--stage",
                    "Stage 01 Build",
                    "--task",
                    "开发：示例",
                    "--status",
                    "/",
                    "--token",
                    token,
                    "--dry-run",
                    "--json",
                    cwd=self.root.parent,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("+", json.loads(result.stdout)["diff"])
                self.assertEqual(self.log.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
