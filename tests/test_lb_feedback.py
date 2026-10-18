"""Regression scenarios from consumer feedback; exercise observable CLI behavior."""

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CLI = Path(__file__).resolve().parents[1] / "bin/lb"
STAGE = "Stage 01 调研"
TASK = "设计：整理采访提纲。 @research"
HUMAN = "人工验证：审阅提纲。 👱"


class FeedbackTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.log = self.root / "log.md"
        self.log.write_text(
            f"# 调研\n\n## 🛫 {STAGE}\n\n- [ ] {TASK}\n    - 技能：interview\n- [ ] {HUMAN}\n"
        )

    def cli(self, *args, code=0):
        result = subprocess.run(
            [sys.executable, str(CLI), "--root", str(self.root), *args, "--json"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, code, result.stderr + result.stdout)
        return json.loads(result.stdout) if result.returncode in (0, 1) else None

    def context(self):
        return self.cli("context", "log.md")

    def write(self, action, task=TASK, token=None, code=0, **options):
        args = [
            "task",
            action,
            "log.md",
            "--stage",
            STAGE,
            "--task",
            task,
            "--token",
            token or self.context()["version_token"],
        ]
        for key, value in options.items():
            args += ["--" + key.replace("_", "-"), value]
        return self.cli(*args, code=code)

    def test_completed_stage_new_task_warns_until_sync(self):
        self.log.write_text("# Demo\n\n## ✅ Stage 01 Demo\n\n待办：\n- [x] Research: previous\n")
        token = self.context()["version_token"]
        self.cli("task", "add", "log.md", "--stage", "Stage 01 Demo", "--text", "Research: new", "--token", token)
        issues = self.cli("check", "log.md", code=1)
        self.assertEqual([i["code"] for i in issues], ["STAGE_EMOJI"])
        self.cli("sync", "log.md", "--token", self.context()["version_token"])
        self.assertEqual(self.cli("check", "log.md"), [])

    def test_write_token_chain_and_preview(self):
        first = self.context()["version_token"]
        preview = self.cli(
            "task",
            "update",
            "log.md",
            "--stage",
            STAGE,
            "--task",
            TASK,
            "--status",
            "/",
            "--token",
            first,
            "--dry-run",
        )
        self.assertEqual(preview["version_token"], first)
        result = self.write("update", status="/", token=first)
        token = result["version_token"]
        self.assertEqual(token, hashlib.sha256(self.log.read_bytes()).hexdigest())
        self.assertNotEqual(token, first)
        synced = self.cli("sync", "log.md", "--token", token)
        self.assertEqual(synced["version_token"], self.context()["version_token"])
        self.write("update", status="x", token=first, code=4)
        no_op = self.cli("sync", "log.md", "--token", synced["version_token"])
        self.assertEqual(no_op["version_token"], synced["version_token"])

    def test_before_task_keeps_child_lines_and_rejects_ambiguity(self):
        args = [
            "task",
            "add",
            "log.md",
            "--stage",
            STAGE,
            "--text",
            "测试：试访。",
            "--before-task",
            HUMAN,
        ]
        self.cli(*args, "--token", self.context()["version_token"])
        self.assertIn(
            "    - 技能：interview\n- [ ] 测试：试访。\n- [ ] " + HUMAN,
            self.log.read_text(),
        )
        self.cli(
            *args,
            "--before-line",
            "7",
            "--token",
            self.context()["version_token"],
            code=2,
        )
        self.log.write_text(self.log.read_text() + f"- [ ] {HUMAN}\n")
        self.cli(
            "task",
            "add",
            "log.md",
            "--stage",
            STAGE,
            "--text",
            "验证：归档。",
            "--before-task",
            HUMAN,
            "--token",
            self.context()["version_token"],
            code=4,
        )

    def test_human_progress_does_not_clear_gate(self):
        self.write("update", task=HUMAN, status="/")
        self.write("update", status="x")
        self.assertEqual(self.context()["next_task"]["text"], HUMAN)
        for status in ("x", "-", " "):
            self.write("update", task=HUMAN, status=status, code=4)
        self.log.write_text(
            self.log.read_text().replace("[/] " + HUMAN, "[ ] 人工验证：历史项")
        )
        self.write("update", task="人工验证：历史项", status="/")
        self.write("update", task="人工验证：历史项", status="x", code=4)

    def test_rewrite_preserves_position_children_and_requires_new_identity(self):
        renamed = "设计：整理问卷提纲。 @research"
        self.write("rewrite", text=renamed, decision="用户改为问卷访谈")
        text = self.log.read_text()
        self.assertIn(f"- [ ] {renamed}\n    - 技能：interview", text)
        self.assertLess(text.index(renamed), text.index(HUMAN))
        self.assertIn("用户改为问卷访谈", text)
        self.write("update", status="/", code=4)
        self.write(
            "rewrite",
            task=renamed,
            text="设计：改归属。 @other",
            decision="未批准归属变化",
            code=4,
        )
        self.write(
            "rewrite", task=HUMAN, text="人工验证：新要求。 👱", decision="改写", code=4
        )
        self.write("update", task=renamed, status="x")
        self.write(
            "rewrite", task=renamed, text=TASK, decision="不能继承已完成证据", code=4
        )

    def test_resolved_cancellation_closes_without_claiming_success(self):
        self.write("update", status="x")
        self.log.write_text(
            self.log.read_text().replace("[ ] " + HUMAN, "[-] " + HUMAN)
        )
        self.assertEqual(self.context()["stages"][0]["derived_emoji"], "🚧")
        self.write(
            "resolve",
            task=HUMAN,
            **{
                "as": "human-cancelled",
                "decision": "用户确认由现场访谈覆盖",
                "note": "无需另行审阅",
            },
        )
        self.cli("sync", "log.md", "--token", self.context()["version_token"])
        self.assertEqual(self.context()["stages"][0]["derived_emoji"], "✅")
        self.assertEqual(self.cli("check", "log.md"), [])
        self.assertIn("取消", self.cli("state", "log.md")["summary"])
        self.assertIn("[-] " + HUMAN, self.log.read_text())
        self.log.write_text(
            self.log.read_text().replace(HUMAN, "人工验证：全新审阅 👱")
        )
        self.assertNotEqual(self.context()["stages"][0]["derived_emoji"], "✅")
        self.assertIn(
            "INVALID_RESOLUTION",
            {x["code"] for x in self.cli("check", "log.md", code=1)},
        )

    def test_resolve_cannot_cancel_open_human_task_or_bypass_preflight(self):
        self.write(
            "resolve",
            task=HUMAN,
            **{"as": "human-cancelled", "decision": "裁定", "note": "理由"},
            code=4,
        )
        self.log.write_text(self.log.read_text() + "    - [ ] 🔮 待讨论：范围\n")
        self.write("rewrite", text="设计：新提纲。 @research", decision="裁定", code=4)

    def test_all_cancelled_can_close_but_unresolved_skip_cannot(self):
        self.log.write_text(f"# 调研\n\n## 🚧 {STAGE}\n\n- [-] {HUMAN}\n")
        self.write(
            "resolve",
            task=HUMAN,
            **{"as": "not-applicable", "decision": "项目取消", "note": "不再适用"},
        )
        self.assertEqual(self.context()["stages"][0]["derived_emoji"], "✅")

    def test_resolution_is_bound_visible_and_preserves_crlf(self):
        self.log.write_bytes(
            f"# 调研\r\n\r\n## 🚧 {STAGE}\r\n\r\n- [-] {HUMAN}\r\n".encode()
        )
        self.write(
            "resolve",
            task=HUMAN,
            **{
                "as": "human-cancelled",
                "decision": "人类明确取消",
                "note": "保留 <!-- 原因文字 -->",
            },
        )
        self.assertNotIn(b"\n", self.log.read_bytes().replace(b"\r\n", b""))
        self.assertIsNotNone(self.context()["stages"][0]["tasks"][0]["resolution"])
        original = self.log.read_text()
        record = next(
            line for line in original.splitlines() if line.startswith("    - 处置：")
        )
        self.log.write_text(original + record + "\n")
        self.assertEqual(self.context()["stages"][0]["derived_emoji"], "🚧")
        self.assertIn(
            "INVALID_RESOLUTION",
            {x["code"] for x in self.cli("check", "log.md", code=1)},
        )
        self.log.write_text(
            original.replace(record, "    ```\n" + record + "\n    ```")
        )
        self.assertEqual(self.context()["stages"][0]["derived_emoji"], "🚧")

    def test_rewrite_refuses_duplicate_text_and_human_role_transfer(self):
        self.log.write_text(self.log.read_text() + "- [ ] 设计：另一项。 @research\n")
        self.write("rewrite", text="设计：另一项。 @research", decision="裁定", code=4)
        self.write(
            "rewrite", text="设计：转交人工。 @research 👱", decision="裁定", code=4
        )
        self.write("rewrite", text=TASK, decision="   ", code=2)

    def test_explicit_assignment_preserves_unassigned_task_and_cas(self):
        old = "验证：复盘实现。"
        new = old + " @sample-app"
        self.log.write_text(
            f"# 调研\n\n## 🚧 {STAGE}\n\n- [/] {old}\n"
            "    - 技能：`/example-review`\n    - 状态：保留人工批注\n"
            f"- [ ] {HUMAN}\n"
        )
        before = self.log.read_bytes()
        token = self.context()["version_token"]
        args = ["task", "rewrite", "log.md", "--stage", STAGE, "--task", old,
                "--text", new, "--decision", "用户明确指定责任仓库", "--token", token]
        self.cli(*args, code=4)
        self.cli(*args, "--assign-repo", "sample-app", "--dry-run")
        self.assertEqual(self.log.read_bytes(), before)
        self.cli(*args, "--assign-repo", "sample-app")
        current = self.log.read_text()
        self.assertIn(f"- [/] {new}\n    - 技能：`/example-review`\n    - 状态：保留人工批注", current)
        self.assertIn(f"- [ ] {HUMAN}", current)
        self.cli(*args, "--assign-repo", "sample-app", code=4)
        self.assertEqual(self.log.read_text(), current)

    def test_assignment_rejects_transfer_mismatch_and_protected_tasks(self):
        for old, new, repo in (
            (TASK, "设计：转移。 @other", "other"),
            ("设计：未定责。", "设计：定责。 @other", "sample-app"),
            ("设计：未定责。", "设计：定责。 @sample-app @other", "sample-app"),
            (HUMAN, "人工验证：审阅提纲。 @sample-app 👱", "sample-app"),
        ):
            for state in (" ", "x", "-"):
                with self.subTest(old=old, state=state):
                    self.log.write_text(f"# 调研\n\n## 🚧 {STAGE}\n\n- [{state}] {old}\n")
                    before = self.log.read_bytes()
                    self.write("rewrite", task=old, text=new, decision="明确决定",
                               assign_repo=repo, code=4)
                    self.assertEqual(self.log.read_bytes(), before)

        for state in ("x", "-"):
            old = "设计：已结项。"
            self.log.write_text(f"# 调研\n\n## 🚧 {STAGE}\n\n- [{state}] {old}\n")
            before = self.log.read_bytes()
            self.write("rewrite", task=old, text=old + " @sample-app",
                       decision="明确决定", assign_repo="sample-app", code=4)
            self.assertEqual(self.log.read_bytes(), before)

    def test_two_logs_never_refresh_shared_human_todo(self):
        companion = self.root / "TODO.md"
        companion.write_bytes(b"# Human navigation\r\n\r\nKeep this note.\r\n")
        second = self.root / "second.md"
        second.write_bytes(self.log.read_bytes())
        original_companion = companion.read_bytes()
        for name in ("log.md", "second.md", "log.md"):
            other = second if name == "log.md" else self.log
            other_before = other.read_bytes()
            token = self.cli("context", name)["version_token"]
            self.cli("task", "note", name, "--stage", STAGE, "--task", TASK,
                     "--kind", "状态", "--text", f"当前候选 {token[:8]}", "--token", token)
            self.assertEqual(other.read_bytes(), other_before)
            self.assertEqual(companion.read_bytes(), original_companion)
        companion.unlink()
        self.cli("sync", "log.md", "--token", self.context()["version_token"])
        self.assertFalse(companion.exists())


if __name__ == "__main__":
    unittest.main()
