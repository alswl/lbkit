"""Task insertion at confirmed checklist boundaries."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CLI = Path(__file__).resolve().parents[1] / "scripts" / "lb.py"
LOG = "projects/demo/docs/log.md"
STAGE = "Stage 01 Demo"


class TaskAddTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.log = self.root / LOG
        self.log.parent.mkdir(parents=True)
        self.log.write_text(
            f"# Demo\n\n## 总览\n\n- [ ] 旧全局摘要\n\n## 🚧 {STAGE}\n\n待办：\n\n"
            "- [x] 开发：第一项\n    - 产物：一\n- [ ] 测试：第二项\n\n验收口径：保持。\n",
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

    def token(self) -> str:
        return json.loads(self.cli("context", LOG, "--json").stdout)["version_token"]

    def args(self, text: str, *extra: str) -> tuple[str, ...]:
        return (
            "task",
            "add",
            LOG,
            "--stage",
            STAGE,
            "--text",
            text,
            "--token",
            self.token(),
            *extra,
        )

    def test_append_before_footer_and_refresh_todo(self) -> None:
        self.assertEqual(self.cli("todo", LOG).returncode, 0)
        before = self.log.read_bytes()
        args = self.args("验证：第三项")
        preview = self.cli(*args, "--dry-run", "--json")
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertIn("+- [ ] 验证：第三项", json.loads(preview.stdout)["diff"])
        self.assertEqual(self.log.read_bytes(), before)
        self.assertEqual(self.cli(*args).returncode, 0)
        content = self.log.read_text(encoding="utf-8")
        self.assertLess(content.index("测试：第二项"), content.index("验证：第三项"))
        self.assertLess(
            content.index("验证：第三项"), content.index("验收口径：保持。")
        )
        self.assertEqual(self.cli(*self.args("验证：第三项")).returncode, 4)

    def test_insert_before_exact_task_line(self) -> None:
        result = self.cli(*self.args("测试：中间项", "--before-line", "13"))
        self.assertEqual(result.returncode, 0, result.stderr)
        content = self.log.read_text(encoding="utf-8")
        self.assertLess(content.index("产物：一"), content.index("测试：中间项"))
        self.assertLess(content.index("测试：中间项"), content.index("测试：第二项"))
        self.assertEqual(
            self.cli(*self.args("测试：错误行", "--before-line", "3")).returncode, 4
        )

    def test_empty_stage_requires_todo_anchor(self) -> None:
        self.log.write_text(
            "# Demo\n\n## 🛫 Stage 01 Demo\n\n待办：\n", encoding="utf-8"
        )
        self.assertEqual(self.cli(*self.args("开发：开始")).returncode, 0)
        self.assertIn("待办：\n- [ ] 开发：开始", self.log.read_text(encoding="utf-8"))
        self.log.write_text("# Demo\n\n## 🛫 Stage 01 Demo\n", encoding="utf-8")
        self.assertEqual(self.cli(*self.args("开发：开始")).returncode, 4)

    def test_preflight_blocks_new_task(self) -> None:
        content = self.log.read_text(encoding="utf-8").replace(
            "- [ ] 测试：第二项", "- [ ] 🔮 测试：第二项"
        )
        self.log.write_text(content, encoding="utf-8")
        before = self.log.read_bytes()
        result = self.cli(*self.args("测试：新事项"))
        self.assertEqual(result.returncode, 4)
        self.assertIn("preflight", result.stderr)
        self.assertEqual(self.log.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
