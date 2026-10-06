"""lb skills usage: skill calls from sessions inside logbook work dirs."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CLI = Path(__file__).resolve().parents[1] / "scripts" / "lb.py"


def jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


class SkillUsageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name).resolve()
        self.home, self.root = base / "home", base / "logbooks"
        work, other = base / "work", base / "other"
        for d in (work, other, self.home / ".claude" / "skills" / "spec-status"):
            d.mkdir(parents=True)
        docs = self.root / "projects" / "demo" / "docs"
        docs.mkdir(parents=True)
        (docs / "log.md").write_text(
            f"# Demo\n\n工作目录：\n\n- local\n  - `{work}`\n\n"
            "## 🛫 Stage 01 Build\n\n- [ ] 开发：示例\n",
            encoding="utf-8",
        )
        tool = {
            "type": "tool_use",
            "name": "Skill",
            "input": {"skill": "speckit-implement", "args": "T001"},
        }
        jsonl(
            self.home / ".claude" / "projects" / "w" / "a.jsonl",
            [
                {"cwd": str(work / "sub"), "timestamp": "2026-10-02T00:00", "message": {"content": [tool]}},
                {"cwd": str(work), "timestamp": "2026-10-03T00:00", "message": {"content": "<command-name>/spec-status</command-name>"}},
                {"cwd": str(work), "timestamp": "2026-10-03T00:01", "message": {"content": "<command-name>/model</command-name>"}},
                {"cwd": str(other), "timestamp": "2026-10-03T00:02", "message": {"content": [tool]}},
                {"cwd": str(work), "timestamp": "2026-09-01T00:00", "message": {"content": [tool]}},
            ],
        )
        read = {"type": "function_call", "arguments": '{"cmd": "sed -n 1,80p ~/.codex/skills/d2/SKILL.md"}'}
        jsonl(
            self.home / ".codex" / "sessions" / "2026" / "10" / "04" / "s.jsonl",
            [
                {"timestamp": "2026-10-04T00:00", "payload": {"cwd": str(work)}},
                {"timestamp": "2026-10-04T00:01", "payload": read},
                {"timestamp": "2026-10-04T00:02", "payload": read},
            ],
        )
        jsonl(
            self.home / ".codex" / "sessions" / "2026" / "10" / "04" / "t.jsonl",
            [
                {"timestamp": "2026-10-04T00:00", "payload": {"cwd": str(other)}},
                {"timestamp": "2026-10-04T00:01", "payload": read},
            ],
        )

    def test_reports_only_work_dir_sessions_since_date(self):
        result = subprocess.run(
            [sys.executable, str(CLI), "--root", str(self.root), "skills", "usage", "--since", "2026-10-01", "--json"],
            env={**os.environ, "HOME": str(self.home)},
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        events = json.loads(result.stdout)["events"]
        self.assertEqual(
            [(e["runtime"], e["how"], e["skill"]) for e in events],
            [
                ("claude", "tool", "speckit-implement"),
                ("claude", "command", "spec-status"),
                ("codex", "read", "d2"),
            ],
        )
        self.assertEqual(events[0]["args"], "T001")


if __name__ == "__main__":
    unittest.main()
