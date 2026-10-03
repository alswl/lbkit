"""Tests for the `todo` human view and write-safety checks.

Covers the `todo` view (snapshot/render/refresh), same-text duplicate
task detection with ambiguous-write refusal, and home-relative link
targets in `lb check`.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("lb", ROOT / "scripts" / "lb.py")
lb = importlib.util.module_from_spec(_spec)
sys.modules["lb"] = lb  # dataclasses look the module up in sys.modules
_spec.loader.exec_module(lb)


def write_logbook(directory: Path) -> Path:
    body = (
        "# Demo\n\n"
        "## 🚧 Stage 01 Demo\n\n"
        "目标：demo\n\n"
        "待办：\n\n"
        "- [ ] 第一个任务\n"
        "    🚨 需负责人处理：做某事。完成标志：xx。解除条件：yy。\n"
        "- [/] Agent 任务\n"
        "- [ ] 人工验证：某人工步骤 👱\n"
        "- [x] 已完成\n"
        "- [ ] 第一个任务\n"
        "- [x] 已完成\n"
    )
    directory.joinpath("docs").mkdir(parents=True)
    path = directory / "docs" / "logbook.md"
    path.write_text(body, encoding="utf-8")
    return path


class TodoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "projects" / "demo"
        self.root = Path(self.tmp.name)
        self.path = write_logbook(self.dir)
        self.doc = lb.parse(self.path, self.root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_snapshot_sections(self) -> None:
        snap = lb.todo_snapshot(self.doc)
        self.assertEqual(snap["logbook"], "projects/demo/docs/logbook.md")
        self.assertEqual(len(snap["alarms"]), 1)
        self.assertIn("需负责人处理", snap["alarms"][0]["blockers"][0])
        self.assertEqual(len(snap["human_pending"]), 1)
        self.assertTrue(snap["human_pending"][0]["human"])
        self.assertEqual(snap["next_task"]["text"], "第一个任务")
        self.assertEqual(len(snap["doing"]), 1)
        self.assertEqual(snap["todo"][0]["text"], "第一个任务")

    def test_alarm_on_task_first_line(self) -> None:
        self.path.write_text(
            self.path.read_text(encoding="utf-8").replace(
                "- [ ] 第一个任务", "- [ ] 🚨 第一个任务", 1
            ),
            encoding="utf-8",
        )
        snap = lb.todo_snapshot(lb.parse(self.path, self.root))
        self.assertEqual(len(snap["alarms"]), 1)
        self.assertEqual(snap["alarms"][0]["blockers"][0], "🚨 第一个任务")

    def test_render_contains_all_views(self) -> None:
        rendered = lb.render_todo(lb.todo_snapshot(self.doc))
        for needle in (
            "需负责人处理",
            "人工验证：某人工步骤",
            "下一项",
            "进行中",
            "bin/lb todo",
            "手改会被覆盖",
        ):
            self.assertIn(needle, rendered)

    def test_refresh_requires_existing_todo(self) -> None:
        self.assertIsNone(lb.refresh_todo(self.doc))
        target = self.dir / "docs" / "TODO.md"
        target.write_text("# stale\n", encoding="utf-8")
        self.assertEqual(lb.refresh_todo(self.doc), target)
        self.assertIn("下一项", target.read_text(encoding="utf-8"))

    def test_refresh_reparses_disk_not_stale_doc(self) -> None:
        target = self.dir / "docs" / "TODO.md"
        target.write_text("# placeholder\n", encoding="utf-8")
        self.path.write_text(
            self.path.read_text(encoding="utf-8").replace(
                "- [/] Agent 任务", "- [x] Agent 任务"
            ),
            encoding="utf-8",
        )
        lb.refresh_todo(self.doc)  # doc object predates the edit
        text = target.read_text(encoding="utf-8")
        self.assertNotIn("## 进行中", text)


class DuplicateTextTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.path = write_logbook(self.root / "projects" / "demo")
        self.doc = lb.parse(self.path, self.root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_check_flags_duplicate_task_text(self) -> None:
        problems = lb.check(self.doc)
        dupes = [
            p for p in problems if p["code"] == "DUPLICATE_TASK_TEXT"
        ]  # 第一个任务 ×2；已完成×2 全 [x] 不告警
        messages = " ".join(p["message"] for p in dupes)
        self.assertIn("第一个任务", messages)

    def test_no_duplicate_no_flag(self) -> None:
        dedup = self.path.read_text(encoding="utf-8").rpartition("第一个任务")
        self.path.write_text(dedup[0] + "另一个任务" + dedup[2], encoding="utf-8")
        doc = lb.parse(self.path, self.root)
        problems = lb.check(doc)
        self.assertEqual(
            [p for p in problems if p["code"] == "DUPLICATE_TASK_TEXT"], []
        )

    def test_ambiguous_write_refused(self) -> None:
        import argparse

        args = argparse.Namespace(
            root=str(self.root),
            log="projects/demo/docs/logbook.md",
            stage="Stage 01 Demo",
            task="第一个任务",
            status="x",
            token=lb.parse(self.path, self.root).token,
            dry_run=True,
        )
        with self.assertRaises(lb.LbError) as caught:
            lb.cmd_task_update(args)
        self.assertEqual(caught.exception.code, lb.EXIT_REFUSED)  # ambiguous refusal


class HomeLinkTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.path = write_logbook(self.root / "projects" / "demo")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_home_relative_link_is_outside_not_missing(self) -> None:
        self.path.write_text(
            self.path.read_text(encoding="utf-8").replace(
                "第\n", "第\n    - 产物：demo `~/ws/somewhere/file.md`\n", 1
            ),
            encoding="utf-8",
        )
        doc = lb.parse(self.path, self.root)
        problems = lb.check(doc)
        missing = [
            p
            for p in problems
            if p["code"] == "LOCAL_LINK_MISSING" and "~" in p["message"]
        ]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
