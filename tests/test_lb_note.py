"""Task note behavior exercised through the public CLI."""

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
TASK = "开发：交付结果。 @core"


class TaskNoteTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.log = self.root / LOG
        self.log.parent.mkdir(parents=True)
        self.log.write_text(
            f"# Demo\n\n## 🚧 {STAGE}\n\n- [/] {TASK}\n"
            "    - 产物：既有报告\n\n- [ ] 人工验证：确认结果。 👱\n",
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

    def note_args(self, token: str, *extra: str) -> tuple[str, ...]:
        return (
            "task",
            "note",
            LOG,
            "--stage",
            STAGE,
            "--task",
            TASK,
            "--token",
            token,
            *extra,
        )

    def test_note_appends_after_existing_children_and_refreshes_alarm(self) -> None:
        todo = self.log.parent / "TODO.md"
        self.assertEqual(self.cli("todo", LOG).returncode, 0)
        before = self.log.read_bytes()
        args = self.note_args(
            self.token(), "--kind", "阻塞", "--text", "🚨 请提供验收账号；提供后恢复。"
        )
        preview = self.cli(*args, "--dry-run", "--json")
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertEqual(self.log.read_bytes(), before)
        self.assertIn("+    - 🚨 阻塞：", json.loads(preview.stdout)["diff"])
        self.assertEqual(self.cli(*args).returncode, 0)
        content = self.log.read_text(encoding="utf-8")
        self.assertLess(content.index("产物：既有报告"), content.index("🚨 阻塞："))
        self.assertLess(content.index("🚨 阻塞："), content.index("人工验证：确认结果"))
        self.assertIn("请提供验收账号", todo.read_text(encoding="utf-8"))
        self.assertEqual(
            self.cli(
                *self.note_args(
                    self.token(),
                    "--kind",
                    "阻塞",
                    "--text",
                    "🚨 请提供验收账号；提供后恢复。",
                )
            ).returncode,
            4,
        )

    def test_note_respects_crlf_and_rejects_human_or_preflight(self) -> None:
        self.log.write_bytes(self.log.read_bytes().replace(b"\n", b"\r\n"))
        args = self.note_args(
            self.token(), "--kind", "交接", "--text", "交接：测试已接收"
        )
        self.assertEqual(self.cli(*args).returncode, 0)
        self.assertIn("    - 交接：测试已接收\r\n".encode(), self.log.read_bytes())
        human = self.cli(
            "task",
            "note",
            LOG,
            "--stage",
            STAGE,
            "--task",
            "人工验证：确认结果。 👱",
            "--text",
            "说明",
            "--token",
            self.token(),
        )
        self.assertEqual(human.returncode, 4)
        blocked = self.log.read_text(encoding="utf-8").replace("- [/]", "- [/] 🔮", 1)
        self.log.write_text(blocked, encoding="utf-8")
        result = self.cli(*self.note_args(self.token(), "--text", "说明"))
        self.assertEqual(result.returncode, 4)
        self.assertIn("preflight", result.stderr)

    def test_artifact_uses_task_tail(self) -> None:
        result = self.cli(
            "task",
            "artifact",
            LOG,
            "--stage",
            STAGE,
            "--task",
            TASK,
            "--artifact",
            "产物：新报告",
            "--token",
            self.token(),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        content = self.log.read_text(encoding="utf-8")
        self.assertLess(content.index("产物：既有报告"), content.index("产物：新报告"))

    def test_candidate_check_refuses_new_missing_local_link(self) -> None:
        before = self.log.read_bytes()
        result = self.cli(
            *self.note_args(
                self.token(), "--kind", "产物", "--text", "[缺失报告](missing.md)"
            )
        )
        self.assertEqual(result.returncode, 4)
        self.assertIn("LOCAL_LINK_MISSING", result.stderr)
        self.assertEqual(self.log.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
