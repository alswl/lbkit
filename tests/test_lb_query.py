"""Focused task queries over delivery stages."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CLI = Path(__file__).resolve().parents[1] / "scripts" / "lb.py"
LOG = "projects/demo/docs/log.md"


class TaskQueryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.log = self.root / LOG
        self.log.parent.mkdir(parents=True)
        self.log.write_text(
            "# Demo\n\n## 总览\n\n- [ ] 人工验证：旧全局摘要 👱\n\n"
            "## 🚧 Stage 01 实现\n\n- [x] 开发：已交付\n"
            "- [/] 测试：进行中 @core\n"
            "- [ ] 人工验证：验收 👱\n",
            encoding="utf-8",
        )

    def cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CLI), "--root", str(self.root), *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )

    def test_list_filters_delivery_tasks(self) -> None:
        result = self.cli("task", "list", LOG, "--human", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = json.loads(result.stdout)
        self.assertEqual([row["text"] for row in rows], ["人工验证：验收 👱"])
        result = self.cli("task", "list", LOG, "--status", "in-progress", "--json")
        self.assertEqual(json.loads(result.stdout)[0]["repositories"], ["core"])
        self.assertEqual(
            len(json.loads(self.cli("task", "list", LOG, "--json").stdout)), 3
        )

    def test_next_and_all_done(self) -> None:
        result = self.cli("task", "next", LOG, "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["text"], "测试：进行中 @core")
        self.log.write_text(
            self.log.read_text(encoding="utf-8")
            .replace("- [/] 测试", "- [x] 测试")
            .replace("- [ ] 人工验证：验收", "- [x] 人工验证：验收"),
            encoding="utf-8",
        )
        self.assertIsNone(json.loads(self.cli("task", "next", LOG, "--json").stdout))

    def test_discovery_uses_configured_project_directory(self) -> None:
        alternate = self.root / "records/demo/docs/log.md"
        alternate.parent.mkdir(parents=True)
        alternate.write_bytes(self.log.read_bytes())
        listed = self.cli("list", "--projects-dir", "records", "--json")
        self.assertEqual(listed.returncode, 0, listed.stderr)
        self.assertEqual(json.loads(listed.stdout)["logbooks"], ["records/demo/docs/log.md"])
        tasks = self.cli("task", "list", "--projects-dir", "records", "--json")
        self.assertEqual(tasks.returncode, 0, tasks.stderr)
        self.assertEqual(len(json.loads(tasks.stdout)), 3)
        invalid = self.cli("list", "--projects-dir", "../outside", "--json")
        self.assertEqual(invalid.returncode, 3)


if __name__ == "__main__":
    unittest.main()
