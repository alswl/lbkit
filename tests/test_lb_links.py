"""link add / link rewrite behavior exercised through the public CLI."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CLI = Path(__file__).resolve().parents[1] / "scripts" / "lb.py"
LOG = "projects/demo/docs/log.md"


class LinkTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.log = self.root / LOG
        self.log.parent.mkdir(parents=True)
        self.outside = tempfile.TemporaryDirectory()
        self.addCleanup(self.outside.cleanup)
        self.main = Path(self.outside.name).resolve() / "main"
        (self.main / "specs").mkdir(parents=True)
        (self.main / "specs" / "tasks.md").write_text("x", encoding="utf-8")
        wt = Path(self.outside.name).resolve() / "wt"
        self.log.write_text(
            "# Demo\n\n## 🚧 Stage 01 One\n\n相关链接：\n\n"
            f"- [规格](file://{wt}/specs/tasks.md)\n\n待办：\n\n- [/] 开发：交付。\n\n"
            "## 🛫 Stage 02 Two\n\n待办：\n\n- [ ] 开发：后续。\n\n"
            f"```\n[围栏](file://{wt}/specs/tasks.md)\n```\n",
            encoding="utf-8",
        )
        self.wt = wt

    def cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CLI), "--root", str(self.root), *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )

    def token(self) -> str:
        return json.loads(self.cli("context", LOG, "--json").stdout)["version_token"]

    def add(self, stage: str, link: str) -> subprocess.CompletedProcess[str]:
        return self.cli(
            "link", "add", LOG, "--stage", stage, "--link", link, "--token", self.token()
        )

    def test_add_appends_to_block_or_creates_it_before_todo(self) -> None:
        self.assertEqual(self.add("Stage 01 One", "[PR](https://example.com/pr/1)").returncode, 0)
        self.assertEqual(self.add("Stage 02 Two", "[PR](https://example.com/pr/2)").returncode, 0)
        text = self.log.read_text(encoding="utf-8")
        self.assertIn("tasks.md)\n- [PR](https://example.com/pr/1)\n\n待办：", text)
        self.assertIn(
            "## 🛫 Stage 02 Two\n\n相关链接：\n\n- [PR](https://example.com/pr/2)\n\n待办：",
            text,
        )
        self.assertEqual(self.add("Stage 01 One", "[PR](https://example.com/pr/1)").returncode, 4)
        self.assertEqual(self.add("Stage 01 One", "not a link").returncode, 2)

    def test_rewrite_verifies_only_rewritten_targets(self) -> None:
        args = ("link", "rewrite", LOG, "--from", f"file://{self.wt}/", "--to")
        missing = self.cli(*args, f"file://{self.main}/nope/", "--token", self.token())
        self.assertEqual(missing.returncode, 4)
        self.assertIn("rewritten link target missing", missing.stderr)
        result = self.cli(*args, f"file://{self.main}/", "--token", self.token(), "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(json.loads(result.stdout)["rewritten"]), 1)
        text = self.log.read_text(encoding="utf-8")
        self.assertIn(f"[规格](file://{self.main}/specs/tasks.md)", text)
        self.assertIn(f"[围栏](file://{self.wt}/specs/tasks.md)", text)


if __name__ == "__main__":
    unittest.main()
