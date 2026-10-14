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

    def test_protected_detail_append_replace_and_canonical_skills(self):
        for kind, value in (("Source", "💬 owner 2026-10-14 new input"), ("Acceptance", "current result must pass"), ("Skills", "example-skill, `/another-skill`")):
            result = self.cli(*self.note_args(self.token(), "--kind", kind, "--text", value), "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
        context = json.loads(self.cli("context", LOG, "--json").stdout)
        task = context["stages"][0]["tasks"][0]
        annotations = task["annotations"]
        skills = next(a for a in annotations if a["kind"] == "skills")
        self.assertEqual(skills["names"], ["example-skill", "another-skill"])
        self.assertIn("    - 技能：`/example-skill`、`/another-skill`", self.log.read_text())
        acceptance = next(a for a in annotations if a["kind"] == "acceptance")
        token = self.token()
        result = self.cli(*self.note_args(token, "--kind", "Acceptance", "--replace-line", str(acceptance["line"]), "--text", "revised condition"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("current result must pass", self.log.read_text())
        self.assertIn("💬 owner", self.log.read_text())
        self.assertEqual(self.cli(*self.note_args(token, "--kind", "Acceptance", "--text", "stale")).returncode, 4)
        before = self.log.read_bytes()
        result = self.cli(*self.note_args(self.token(), "--kind", "Source", "--replace-line", str(acceptance["line"]), "--text", "wrong kind"))
        self.assertEqual(result.returncode, 4)
        self.assertEqual(self.log.read_bytes(), before)

    def test_empty_or_hidden_task_details_refuse_without_hiding_human_gate(self):
        before = self.log.read_bytes()
        for text in ("Source:", "Acceptance: <!-- hide the human gate", "Skills: <!-- hide"):
            with self.subTest(text=text):
                result = self.cli(*self.note_args(self.token(), "--text", text))
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(self.log.read_bytes(), before)
                self.assertEqual(len(json.loads(self.cli("context", LOG, "--json").stdout)["stages"][0]["tasks"]), 2)

    def test_replacement_preserves_human_comment_and_line_endings(self):
        self.log.write_bytes((f"# Demo\r\n\r\n## 🚧 {STAGE}\r\n\r\n- [/] {TASK}\r\n    - 验收：old <!-- human comment -->").encode())
        result = self.cli(*self.note_args(self.token(), "--kind", "Acceptance", "--replace-line", "6", "--text", "new"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.log.read_bytes().endswith("验收：new <!-- human comment -->".encode()))
        self.assertNotIn(b"\n", self.log.read_bytes().replace(b"\r\n", b""))

    def test_settled_condition_matrix_blocks_append_and_replace(self):
        for state in ("x", "-"):
            with self.subTest(state=state):
                self.log.write_text(f"# Demo\n\n## 🚧 {STAGE}\n\n- [{state}] {TASK}\n    - 验收：old condition\n")
                before = self.log.read_bytes()
                for kind in ("Source", "Acceptance"):
                    for replacement in ((), ("--replace-line", "6")):
                        result = self.cli(*self.note_args(self.token(), "--kind", kind, "--text", "new", *replacement))
                        self.assertEqual(result.returncode, 4, result.stderr)
                        self.assertEqual(self.log.read_bytes(), before)
                result = self.cli(*self.note_args(self.token(), "--kind", "Skills", "--text", "example-skill"))
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_additive_acceptance_is_conjunctive_and_raw_skills_validate(self):
        for value in ("first condition", "second condition"):
            result = self.cli(*self.note_args(self.token(), "--kind", "验收", "--text", value))
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("first condition", self.log.read_text())
        self.assertIn("second condition", self.log.read_text())
        before = self.log.read_bytes()
        result = self.cli(*self.note_args(self.token(), "--text", "技能：valid ??? malformed"))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.log.read_bytes(), before)

    def test_note_appends_preserving_existing_companion(self) -> None:
        todo = self.log.parent / "TODO.md"
        todo.write_bytes(b"human content\r\n")
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
        self.assertEqual(todo.read_bytes(), b"human content\r\n")
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

    def test_human_task_accepts_only_status_note(self) -> None:
        human = "人工验证：确认结果。 👱"
        base = ("task", "note", LOG, "--stage", STAGE, "--task", human)
        refused = self.cli(*base, "--kind", "交接", "--text", "x", "--token", self.token())
        self.assertEqual(refused.returncode, 4)
        result = self.cli(
            *base, "--kind", "状态", "--text", "证书已就绪", "--token", self.token()
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(
            self.log.read_text(encoding="utf-8").endswith(
                "- [ ] 人工验证：确认结果。 👱\n    - 状态：证书已就绪\n"
            )
        )

    def test_artifact_adds_missing_label(self) -> None:
        result = self.cli(
            "task",
            "artifact",
            LOG,
            "--stage",
            STAGE,
            "--task",
            TASK,
            "--artifact",
            "新报告",
            "--token",
            self.token(),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("    - 产物：新报告\n", self.log.read_text(encoding="utf-8"))

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
