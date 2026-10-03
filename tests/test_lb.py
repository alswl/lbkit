import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

CLI = Path(__file__).parents[1] / "scripts" / "lb.py"
SPEC = importlib.util.spec_from_file_location("lb_under_test", CLI)
LB = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = LB
SPEC.loader.exec_module(LB)

DOC = """# Demo

工作目录：

- local
  - `~/ws/demo`
- remote `build-host`
  - `~/ws/demo`

## 🛫 Stage 01 Build

目标：保留这些中文正文，不应改动。
相关链接：
- [outside](https://example.invalid/a)
- [missing](missing.md)
待办：
- [/] 开发：运行中任务。 @core 🤖️
    - 既有产物
- [-] 测试：历史不适用。
- [ ] 人工验证：人类确认。 👱

```md
## ✅ Stage 99 Fake
- [x] 开发：围栏任务
```

## ✅ Stage 02 Done

- [x] 开发：已完成。
"""


class LbCliTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / "repo"
        self.log = self.root / "projects" / "demo" / "docs" / "log.md"
        self.log.parent.mkdir(parents=True)
        self.log.write_text(DOC, encoding="utf-8")
        (self.root / "projects" / "demo" / "thinking").mkdir()
        (self.root / "projects" / "demo" / "thinking" / "log.md").write_text(
            "# not log", encoding="utf-8"
        )
        self.outside = self.base / "outside.md"

    def tearDown(self):
        self.temp.cleanup()

    def cli(self, *args):
        return subprocess.run(
            [sys.executable, str(CLI), "--root", str(self.root), *args],
            text=True,
            capture_output=True,
            check=False,
        )

    def payload(self, *args):
        result = self.cli(*args, "--json")
        return result, json.loads(result.stdout)

    def token(self):
        _, value = self.payload("context", "projects/demo/docs/log.md")
        return value["version_token"]

    def test_list_context_and_fences(self):
        result, listed = self.payload("list")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(listed["logbooks"], ["projects/demo/docs/log.md"])
        _, data = self.payload("context", "projects/demo/docs/log.md")
        self.assertEqual(data["next_task"]["state"], "/")
        self.assertEqual(data["next_task"]["repositories"], ["core"])
        self.assertEqual(len(data["stages"]), 2)
        self.assertEqual(
            data["stages"][0]["tasks"][0]["text"], "开发：运行中任务。 @core 🤖️"
        )
        self.assertTrue(data["stages"][0]["tasks"][2]["human"])
        self.assertEqual(data["work_directories"][1]["machine"], "remote `build-host`")

    def test_check_and_sync_preserves_body(self):
        result, issues = self.payload("check", "projects/demo/docs/log.md")
        self.assertEqual(result.returncode, 1)
        self.assertIn("SKIPPED_EXPLICIT", {i["code"] for i in issues})
        before = self.log.read_bytes()
        result = self.cli(
            "sync", "projects/demo/docs/log.md", "--token", self.token(), "--dry-run"
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(before, self.log.read_bytes())
        self.assertIn("--- projects/demo/docs/log.md", result.stdout)
        result, dry = self.payload(
            "sync", "projects/demo/docs/log.md", "--token", self.token(), "--dry-run"
        )
        self.assertIn("diff", dry)
        self.assertEqual(
            self.cli(
                "sync", "projects/demo/docs/log.md", "--token", self.token()
            ).returncode,
            0,
        )
        after = self.log.read_text(encoding="utf-8")
        self.assertIn("## 🚧 Stage 01 Build", after)
        self.assertIn("目标：保留这些中文正文，不应改动。", after)
        self.assertIn("## ✅ Stage 02 Done", after)

    def test_ambiguity_version_and_human_artifact_refused(self):
        text = self.log.read_text(encoding="utf-8").replace(
            "开发：已完成。", "开发：运行中任务。 @core 🤖️"
        )
        self.log.write_text(text, encoding="utf-8")
        token = self.token()
        result = self.cli(
            "task",
            "update",
            "projects/demo/docs/log.md",
            "--stage",
            "Stage 01 Build",
            "--task",
            "开发：运行中任务。 @core 🤖️",
            "--status",
            "x",
            "--token",
            token,
        )
        self.assertEqual(
            result.returncode, 0
        )  # stage qualification makes identical text safe
        result = self.cli(
            "task",
            "update",
            "projects/demo/docs/log.md",
            "--stage",
            "Stage 02 Done",
            "--task",
            "开发：运行中任务。 @core 🤖️",
            "--status",
            "x",
            "--token",
            self.token(),
        )
        self.assertEqual(result.returncode, 0)
        stale = token
        result = self.cli(
            "task",
            "artifact",
            "projects/demo/docs/log.md",
            "--stage",
            "Stage 01 Build",
            "--task",
            "人工验证：人类确认。 👱",
            "--artifact",
            "x",
            "--token",
            self.token(),
        )
        self.assertEqual(result.returncode, 4)
        result = self.cli(
            "task",
            "update",
            "projects/demo/docs/log.md",
            "--stage",
            "Stage 01 Build",
            "--task",
            "人工验证：人类确认。 👱",
            "--status",
            "x",
            "--token",
            self.token(),
            "--dry-run",
        )
        self.assertEqual(result.returncode, 4)
        self.assertIn("human-owned", result.stderr)
        result = self.cli(
            "task",
            "update",
            "projects/demo/docs/log.md",
            "--stage",
            "Stage 01 Build",
            "--task",
            "开发：运行中任务。 @core 🤖️",
            "--status",
            "x",
            "--token",
            stale,
        )
        self.assertEqual(result.returncode, 4)

    def test_check_only_external_links_is_advisory(self):
        self.log.write_text(
            "# Demo\n\n## 🛫 Stage 01 Build\n\n相关链接：\n- [PR](https://example.invalid/pr)\n\n待办：\n- [ ] 开发：任务。\n",
            encoding="utf-8",
        )
        result, issues = self.payload("check", "projects/demo/docs/log.md")
        self.assertEqual(result.returncode, 0)
        self.assertEqual([item["code"] for item in issues], ["LINK_UNVERIFIED"])

    def test_todo_all_done_has_no_next_task(self):
        self.log.write_text(
            "# Demo\n\n## ✅ Stage 01 Build\n\n待办：\n- [x] 开发：已完成。\n",
            encoding="utf-8",
        )
        result = self.cli("todo", "projects/demo/docs/log.md", "--dry-run")
        self.assertEqual(result.returncode, 0)
        self.assertIn("- 全部完成", result.stdout)

    def test_todo_skipped_task_is_not_complete(self):
        self.log.write_text(
            "# Demo\n\n## 🚧 Stage 01 Build\n\n待办：\n- [x] 开发：已完成。\n- [-] 验证：待处置。\n",
            encoding="utf-8",
        )
        result = self.cli("todo", "projects/demo/docs/log.md", "--dry-run")
        self.assertEqual(result.returncode, 0)
        self.assertIn("跳过项待处置", result.stdout)
        self.assertNotIn("- 全部完成", result.stdout)

    def test_overview_checklist_is_not_the_next_delivery_task(self):
        self.log.write_text(
            "# Demo\n\n## 总览\n\n- [ ] 人工验证：旧全局清单。\n\n## 🛫 Stage 01 Build\n\n- [ ] 开发：阶段首项。\n",
            encoding="utf-8",
        )
        result, data = self.payload("context", "projects/demo/docs/log.md")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(data["next_task"]["text"], "开发：阶段首项。")
        result, data = self.payload("state", "projects/demo/docs/log.md")
        self.assertEqual(data["next_task"]["text"], "开发：阶段首项。")
        result, data = self.payload("todo", "projects/demo/docs/log.md")
        self.assertEqual(data["human_pending"], [])

    def test_duplicate_in_one_stage_and_unknown_or_nested_checkbox(self):
        self.log.write_text(
            DOC.replace(
                "- [ ] 人工验证：人类确认。 👱",
                "- [ ] 开发：重复。\n- [ ] 开发：重复。\n    - [z] 嵌套伪任务\n- [z] 未知状态",
            ),
            encoding="utf-8",
        )
        result, issues = self.payload("check", "projects/demo/docs/log.md")
        self.assertIn("UNKNOWN_TASK_STATE", {item["code"] for item in issues})
        result = self.cli(
            "task",
            "update",
            "projects/demo/docs/log.md",
            "--stage",
            "Stage 01 Build",
            "--task",
            "开发：重复。",
            "--status",
            "x",
            "--token",
            self.token(),
        )
        self.assertEqual(result.returncode, 4)

    def test_artifact_crlf_and_path_escape(self):
        self.log.write_bytes(DOC.replace("\n", "\r\n").encode())
        (self.log.parent / "report.md").write_text("# report\n", encoding="utf-8")
        before = self.log.read_bytes()
        token = self.token()
        args = (
            "task",
            "artifact",
            "projects/demo/docs/log.md",
            "--stage",
            "Stage 01 Build",
            "--task",
            "开发：运行中任务。 @core 🤖️",
            "--artifact",
            "产物：[报告](report.md)",
            "--token",
            token,
            "--dry-run",
        )
        dry = self.cli(*args)
        self.assertEqual(dry.returncode, 0)
        self.assertIn("+    - 产物", dry.stdout)
        self.assertEqual(before, self.log.read_bytes())
        self.assertEqual(self.cli(*args[:-1]).returncode, 0)
        data = self.log.read_bytes()
        self.assertIn("    - 产物：[报告](report.md)\r\n".encode(), data)
        self.assertNotIn(b"\n", data.replace(b"\r\n", b""))
        self.outside.write_text("# x")
        self.assertEqual(self.cli("context", str(self.outside)).returncode, 3)

    def test_eof_artifact_and_fence_links_are_ignored(self):
        self.log.write_text(
            "# One\n\n## 🛫 Stage 01 One\n\n- [ ] 开发：EOF", encoding="utf-8"
        )
        result = self.cli(
            "task",
            "artifact",
            "projects/demo/docs/log.md",
            "--stage",
            "Stage 01 One",
            "--task",
            "开发：EOF",
            "--artifact",
            "产物",
            "--token",
            self.token(),
        )
        self.assertEqual(result.returncode, 0)
        self.assertTrue(self.log.read_text().endswith("开发：EOF\n    - 产物\n"))
        self.log.write_text(
            DOC
            + "\n````\n# hidden\n[bad](https://ignored.invalid)\n```\nstill fenced\n````\n",
            encoding="utf-8",
        )
        _, issues = self.payload("check", "projects/demo/docs/log.md")
        self.assertNotIn(
            "LINK_UNVERIFIED", [x["code"] for x in issues if x["line"] > 30]
        )

    def test_html_comments_and_strict_fence_closing_are_ignored(self):
        self.log.write_text(
            DOC
            + "\n<!--\n# hidden\n## ⚠️ Stage 88 Comment\n- [x] 开发：隐藏\n[link](https://hidden.invalid)\n-->\n````\n# fence\n``` trailing\n## ⚠️ Stage 77 StillHidden\n````   \n",
            encoding="utf-8",
        )
        _, data = self.payload("context", "projects/demo/docs/log.md")
        self.assertEqual(
            [stage["title"] for stage in data["stages"]],
            ["Stage 01 Build", "Stage 02 Done"],
        )
        _, issues = self.payload("check", "projects/demo/docs/log.md")
        self.assertNotIn(
            "LINK_UNVERIFIED", [x["code"] for x in issues if x["line"] > 30]
        )

    def test_inline_comment_keeps_preceding_task_and_comment_tail_is_reported(self):
        self.log.write_text(
            "# Demo\n\n## 🛫 Stage 01 Build\n\n- [ ] first <!-- note -->\n- [ ] second\n<!-- example\n- [x] hidden\n--> - [ ] ambiguous\n",
            encoding="utf-8",
        )
        _, data = self.payload("context", "projects/demo/docs/log.md")
        self.assertEqual(data["next_task"]["text"], "first <!-- note -->")
        result = self.cli(
            "task",
            "update",
            "projects/demo/docs/log.md",
            "--stage",
            "Stage 01 Build",
            "--task",
            "first <!-- note -->",
            "--status",
            "x",
            "--token",
            self.token(),
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("- [x] first <!-- note -->", self.log.read_text())
        _, issues = self.payload("check", "projects/demo/docs/log.md")
        self.assertIn("COMMENT_STRUCTURE_AMBIGUOUS", {item["code"] for item in issues})

    def test_old_warning_stage_sync_and_directory_body_boundary(self):
        self.log.write_text(
            DOC.replace("## 🛫 Stage 01 Build", "## ⚠️ Stage 01 Build").replace(
                "- remote `build-host`\n  - `~/ws/demo`\n",
                "- remote `build-host`\n  - `~/ws/demo`\n普通正文不属于目录列表。\n",
            ),
            encoding="utf-8",
        )
        _, issues = self.payload("check", "projects/demo/docs/log.md")
        self.assertNotIn("DIRECTORY_FORMAT", {item["code"] for item in issues})
        self.assertEqual(
            self.cli(
                "sync", "projects/demo/docs/log.md", "--token", self.token()
            ).returncode,
            0,
        )
        self.assertIn("## 🚧 Stage 01 Build", self.log.read_text())

    def test_directory_and_outside_link_diagnostics(self):
        self.log.write_text(
            DOC.replace("- local\n  - `~/ws/demo`", "  - `relative/path`").replace(
                "[missing](missing.md)", "[outside](../../../../outside.md)"
            ),
            encoding="utf-8",
        )
        _, issues = self.payload("check", "projects/demo/docs/log.md")
        codes = {item["code"] for item in issues}
        self.assertTrue({"DIRECTORY_GROUP", "DIRECTORY_PATH"}.issubset(codes))
        self.assertIn("LOCAL_LINK_UNVERIFIED", codes)

    def test_symlink_escape_and_real_exit_codes(self):
        self.outside.write_text("# x")
        link = self.root / "projects" / "demo" / "docs" / "escape.md"
        link.symlink_to(self.outside)
        self.assertEqual(
            self.cli("context", "projects/demo/docs/escape.md").returncode, 3
        )
        _, listed = self.payload("list")
        self.assertEqual(listed["logbooks"], ["projects/demo/docs/log.md"])
        self.assertEqual(self.cli("check").returncode, 2)

    def test_symlink_loop_is_a_path_error_not_a_traceback(self):
        loop = self.root / "projects" / "demo" / "docs" / "loop.md"
        loop.symlink_to("loop.md")
        result = self.cli("context", "projects/demo/docs/loop.md")
        self.assertEqual(result.returncode, 3)
        self.assertNotIn("Traceback", result.stderr)

    def test_discovery_skips_external_project_and_write_rechecks_after_fsync(self):
        external = self.base / "external-project"
        (external / "docs").mkdir(parents=True)
        (external / "docs" / "outside.md").write_text(DOC, encoding="utf-8")
        (self.root / "projects" / "escape-project").symlink_to(
            external, target_is_directory=True
        )
        _, listed = self.payload("list")
        self.assertEqual(listed["logbooks"], ["projects/demo/docs/log.md"])
        doc = LB.parse(self.log.resolve(), self.root.resolve())
        changed = doc.text.replace("运行中任务", "已变更任务", 1).encode()
        real_fsync = LB.os.fsync

        def change_source(fd):
            self.log.write_text("# external edit\n", encoding="utf-8")
            real_fsync(fd)

        with (
            mock.patch.object(LB.os, "fsync", side_effect=change_source),
            self.assertRaises(LB.LbError) as raised,
        ):
            LB.write_bytes(doc, changed, False)
        self.assertEqual(raised.exception.code, 4)
        self.assertEqual(self.log.read_text(encoding="utf-8"), "# external edit\n")

    def test_projects_symlink_is_checked_before_iteration_and_io_errors_are_clean(self):
        repo = self.base / "symlink-root"
        repo.mkdir()
        external = self.base / "external-projects"
        external.mkdir()
        (repo / "projects").symlink_to(external, target_is_directory=True)
        with mock.patch.object(
            Path,
            "iterdir",
            side_effect=AssertionError("must not iterate outside projects"),
        ):
            self.assertEqual(LB.discover(repo), [])
        with (
            mock.patch("logbook_cli.cli.parse", side_effect=OSError("read failure")),
            self.assertRaises(SystemExit) as raised,
        ):
            LB.main(["--root", str(self.root), "context", "projects/demo/docs/log.md"])
        self.assertEqual(raised.exception.code, 3)


PREFLIGHT_DOC = """# Pre

工作目录：

- local
  - `~/ws/demo`

## 🚧 Stage 01 Build

目标：demo。

待办：

- [x] 开发：已完成。
- [ ] 🔮 待讨论：形态未定。 @demo
- [ ] 验证：收尾。
    - [ ] 🔮 子项卡点也要拦。
"""


class PreflightGateTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "repo"
        self.log = self.root / "projects" / "demo" / "docs" / "log.md"
        self.log.parent.mkdir(parents=True)
        self.log.write_text(PREFLIGHT_DOC, encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def cli(self, *args):
        return subprocess.run(
            [sys.executable, str(CLI), "--root", str(self.root), *args],
            text=True,
            capture_output=True,
            check=False,
        )

    def payload(self, *args):
        result = self.cli(*args, "--json")
        return result, json.loads(result.stdout)

    def token(self):
        _, value = self.payload("context", "projects/demo/docs/log.md")
        return value["version_token"]

    def test_context_reports_blockers_of_any_indent(self):
        _, data = self.payload("context", "projects/demo/docs/log.md")
        self.assertFalse(data["preflight_clear"])
        self.assertEqual(len(data["preflight_blockers"]), 2)
        self.assertEqual(data["preflight_blockers"][0]["stage"], "Stage 01 Build")
        self.assertEqual(data["preflight_blockers"][1]["indent"], "    ")
        self.assertTrue(data["stages"][0]["tasks"][1]["preflight"])
        self.assertFalse(data["stages"][0]["tasks"][2]["preflight"])

    def test_check_reports_preflight_blocker(self):
        result, issues = self.payload("check", "projects/demo/docs/log.md")
        self.assertEqual(result.returncode, 1)
        codes = {i["code"] for i in issues}
        self.assertIn("PREFLIGHT_BLOCKER", codes)

    def test_writes_refused_while_blocked_and_resume_after_human_resolution(self):
        token = self.token()
        for command in (
            ("sync", "projects/demo/docs/log.md", "--token", token),
            (
                "task",
                "update",
                "projects/demo/docs/log.md",
                "--stage",
                "Stage 01 Build",
                "--task",
                "验证：收尾。",
                "--status",
                "/",
                "--token",
                token,
            ),
            (
                "task",
                "artifact",
                "projects/demo/docs/log.md",
                "--stage",
                "Stage 01 Build",
                "--task",
                "开发：已完成。",
                "--artifact",
                "产物：[x](x.md)",
                "--token",
                token,
            ),
        ):
            result = self.cli(*command)
            self.assertEqual(result.returncode, 4, result.stderr)
            self.assertIn("🔮", result.stderr)
        self.assertIn("- [ ] 验证：收尾。", self.log.read_text(encoding="utf-8"))
        # Human resolves the 🔮 items in the logbook; the gate lifts.
        self.log.write_text(
            PREFLIGHT_DOC.replace("🔮 待讨论：形态未定。", "设计：形态已定。").replace(
                "🔮 子项卡点也要拦。", "子项不再阻塞。"
            ),
            encoding="utf-8",
        )
        result, data = self.payload("context", "projects/demo/docs/log.md")
        self.assertTrue(data["preflight_clear"])
        result = self.cli(
            "task",
            "update",
            "projects/demo/docs/log.md",
            "--stage",
            "Stage 01 Build",
            "--task",
            "验证：收尾。",
            "--status",
            "/",
            "--token",
            self.token(),
        )
        self.assertEqual(result.returncode, 0, result.stderr)


class StateAndSummaryTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "repo"
        self.log = self.root / "projects" / "demo" / "docs" / "log.md"
        self.log.parent.mkdir(parents=True)
        self.log.write_text(
            """# Demo

> 状态：🛫 旧阶段 —— 人类注释保留

工作目录：

- local
  - `~/ws/demo`

## 🛫 Stage 01 Build

目标：demo。

待办：

- [ ] 开发：第一项。
- [x] 测试：已完成。
""",
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp.cleanup()

    def cli(self, *args):
        return subprocess.run(
            [sys.executable, str(CLI), "--root", str(self.root), *args],
            text=True,
            capture_output=True,
            check=False,
        )

    def payload(self, *args):
        result = self.cli(*args, "--json")
        return result, json.loads(result.stdout)

    def token(self):
        _, value = self.payload("context", "projects/demo/docs/log.md")
        return value["version_token"]

    def test_state_snapshot_is_structured(self):
        result, data = self.payload("state", "projects/demo/docs/log.md")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(
            data["summary"], "状态：🚧 Stage 01 Build · 下一项：开发：第一项。"
        )
        self.assertEqual(
            data["overall"],
            {
                "delivery_stages": 1,
                "done": 0,
                "in_flight": 1,
                "not_started": 0,
                "preflight_clear": True,
            },
        )
        self.assertEqual(
            data["stages"][0]["tasks"],
            {"todo": 1, "doing": 0, "done": 1, "skipped": 0, "human_pending": 0},
        )
        self.assertTrue(data["page_status_lines"][0]["owned"])

    def test_sync_rewrites_owned_summary_but_keeps_human_tail(self):
        _, dry = self.payload(
            "sync", "projects/demo/docs/log.md", "--token", self.token(), "--dry-run"
        )
        self.assertEqual(dry["changed_stages"], 1)
        self.assertEqual(dry["summary_updated"], 1)
        self.assertIn("## 🚧 Stage 01 Build", dry["diff"])
        self.assertNotIn("+mo`", dry["diff"])
        self.assertEqual(
            self.cli(
                "sync", "projects/demo/docs/log.md", "--token", self.token()
            ).returncode,
            0,
        )
        text = self.log.read_text(encoding="utf-8")
        self.assertIn("工作目录：\n\n- local\n  - `~/ws/demo`", text)
        self.assertIn(
            "> 状态：🚧 Stage 01 Build · 下一项：开发：第一项。 —— 人类注释保留", text
        )
        self.assertIn("## 🚧 Stage 01 Build", text)

    def test_sync_keeps_free_form_summary_and_never_creates_one(self):
        self.log.write_text(
            self.log.read_text(encoding="utf-8").replace(
                "> 状态：🛫 旧阶段 —— 人类注释保留",
                "> 状态：已按 人类负责人 决定收口，叙事保留",
            ),
            encoding="utf-8",
        )
        _, dry = self.payload(
            "sync", "projects/demo/docs/log.md", "--token", self.token(), "--dry-run"
        )
        self.assertEqual(dry["summary_updated"], 0)
        self.assertEqual(dry["summary_kept_human"], 1)
        self.assertIn(
            "> 状态：已按 人类负责人 决定收口，叙事保留",
            self.log.read_text(encoding="utf-8"),
        )
        self.log.write_text(
            self.log.read_text(encoding="utf-8").replace(
                "> 状态：已按 人类负责人 决定收口，叙事保留", "正文开头"
            ),
            encoding="utf-8",
        )
        self.cli("sync", "projects/demo/docs/log.md", "--token", self.token())
        self.assertNotIn("状态：", self.log.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
