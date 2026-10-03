"""Exercise the documented CLI sequences, without simulating model decisions."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CLI = Path(__file__).resolve().parents[1] / "scripts" / "lb.py"
LOG = "projects/demo/docs/log.md"
STAGE = "Stage 01 交付"
TASK = "开发：提交 `candidate` 与 $(sample) 报告。 @core"
DOC = f"""# 合成航程

目标：这段人类文字应保持原样。

工作目录：无额外目录（仅本日志项目目录）

## 🛫 {STAGE}

目标：交付报告并由人类决定是否接受。

- [ ] {TASK}
- [ ] 人工验证：接受报告。 👱
"""


class SkillCliFlowsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.log = self.root / LOG
        self.log.parent.mkdir(parents=True)
        self.log.write_text(DOC, encoding="utf-8")
        (self.log.parent / "report.md").write_text("# 已固定报告\n", encoding="utf-8")

    def run_cli(self, *args, code=0):
        result = subprocess.run(
            [sys.executable, str(CLI), "--root", str(self.root), *args, "--json"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(result.returncode, code, result.stderr + result.stdout)
        return json.loads(result.stdout) if result.returncode in (0, 1) else None

    def context(self):
        return self.run_cli("context", LOG)

    def task_args(self, action, context, *args):
        return (
            "task",
            action,
            LOG,
            "--stage",
            STAGE,
            "--task",
            TASK,
            "--token",
            context["version_token"],
            *args,
        )

    def write_with_preview(self, *args):
        before = self.log.read_bytes()
        preview = self.run_cli(*args, "--dry-run")
        self.assertIn("diff", preview)
        self.assertEqual(before, self.log.read_bytes())
        self.run_cli(*args)

    def test_received_then_verified_handoff_refreshes_each_token(self):
        first = self.context()
        self.assertEqual(first["next_task"]["text"], TASK)
        self.write_with_preview(*self.task_args("update", first, "--status", "/"))
        received = self.context()
        self.assertNotEqual(first["version_token"], received["version_token"])
        self.write_with_preview("sync", LOG, "--token", received["version_token"])
        self.assertEqual(self.context()["stages"][0]["emoji"], "🚧")

        # This supplied premise represents a completed evidence review, not a CLI decision.
        self.write_with_preview(
            *self.task_args("update", self.context(), "--status", "x")
        )
        self.write_with_preview(
            *self.task_args(
                "artifact", self.context(), "--artifact", "产物：[报告](report.md)"
            )
        )
        self.write_with_preview("sync", LOG, "--token", self.context()["version_token"])
        result = self.context()
        self.assertTrue(result["next_task"]["human"])
        self.assertEqual(result["next_task"]["state"], " ")
        self.assertEqual(result["stages"][0]["emoji"], "🚧")
        expected = DOC.replace("## 🛫", "## 🚧").replace(
            f"- [ ] {TASK}", f"- [x] {TASK}\n    - 产物：[报告](report.md)"
        )
        self.assertEqual(self.log.read_text(encoding="utf-8"), expected)
        self.assertEqual(self.run_cli("check", LOG), [])

    def test_readonly_context_and_check_leave_mismatched_emoji_untouched(self):
        self.log.write_text(
            DOC.replace(f"- [ ] {TASK}", f"- [/] {TASK}"), encoding="utf-8"
        )
        before = self.log.read_bytes()
        context = self.context()
        self.assertEqual(context["stages"][0]["derived_emoji"], "🚧")
        issues = self.run_cli("check", LOG, code=1)
        self.assertTrue(issues)
        self.assertEqual(self.log.read_bytes(), before)

    def test_concurrent_task_rewrite_refuses_previewed_operation(self):
        context = self.context()
        args = self.task_args("update", context, "--status", "x")
        self.run_cli(*args, "--dry-run")
        edited = DOC.replace(TASK, "开发：交付新版报告。 @core")
        self.log.write_text(edited, encoding="utf-8")
        self.run_cli(*args, code=4)
        fresh = self.context()
        # Refreshing the token does not restore the old task identity.
        self.run_cli(*self.task_args("update", fresh, "--status", "x"), code=4)
        self.assertEqual(self.log.read_text(encoding="utf-8"), edited)

    def test_partial_write_can_resume_without_reappending_artifact(self):
        old = self.context()
        self.write_with_preview(
            *self.task_args("artifact", old, "--artifact", "产物：[报告](report.md)")
        )
        before_retry = self.log.read_bytes()
        self.run_cli("sync", LOG, "--token", old["version_token"], code=4)
        self.assertEqual(self.log.read_bytes(), before_retry)
        # Read back the successful step before deciding what remains to run.
        self.assertEqual(
            self.log.read_text(encoding="utf-8").count("产物：[报告](report.md)"), 1
        )
        fresh = self.context()
        self.run_cli("sync", LOG, "--token", fresh["version_token"])
        self.assertEqual(
            self.log.read_text(encoding="utf-8").count("产物：[报告](report.md)"), 1
        )


if __name__ == "__main__":
    unittest.main()
