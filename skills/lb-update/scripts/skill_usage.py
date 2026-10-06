#!/usr/bin/env python3
"""List skills actually invoked in Claude Code and Codex sessions.

Only sessions whose working directory lies inside a logbook's registered
local work directory (or the logbooks repository itself) are reported, so
unrelated projects in the transcript stores are never surfaced.

    python3 .lbkit/skills/lb-update/scripts/skill_usage.py [--since 2026-10-01] [--json]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

KIT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(KIT / "src"))

from logbook_cli.document import context, discover, parse, root_path  # noqa: E402

HOME = Path.home()
COMMAND_RE = re.compile(r"<command-name>/?([\w:.-]+)</command-name>")
SKILL_READ_RE = re.compile(r"skills/([\w.-]+)/SKILL\.md")


def work_dirs(root: Path, projects_dir: str) -> list[Path]:
    dirs = {root}
    for path in discover(root, projects_dir):
        for group in context(parse(path, root))["work_directories"]:
            if group["machine"] != "local":
                continue
            for item in group["paths"]:
                dirs.add(Path(item["path"]).expanduser().resolve())
    return sorted(dirs)


def inside(cwd: str | None, dirs: list[Path]) -> bool:
    if not cwd:
        return False
    path = Path(cwd).resolve()
    return any(path == d or d in path.parents for d in dirs)


def is_skill(name: str, cwd: str) -> bool:
    """User-typed slash commands include built-ins such as /model; keep skills."""
    bases = [HOME / ".claude", HOME / ".agents", HOME / ".codex", Path(cwd) / ".claude"]
    return any(
        (b / "skills" / name).is_dir() or (b / "commands" / f"{name}.md").is_file()
        for b in bases
    )


def records(path: Path):
    with path.open(encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def claude_events(dirs: list[Path], since: str):
    for path in (HOME / ".claude" / "projects").glob("*/*.jsonl"):
        for item in records(path):
            cwd, time = item.get("cwd"), item.get("timestamp", "")
            if time < since or not inside(cwd, dirs):
                continue
            message = item.get("message") or {}
            content = message.get("content")
            if isinstance(content, str):
                for name in COMMAND_RE.findall(content):
                    if is_skill(name, cwd):
                        yield "claude", "command", name, "", time, cwd, path
            elif isinstance(content, list):
                for part in content:
                    if (
                        isinstance(part, dict)
                        and part.get("type") == "tool_use"
                        and part.get("name") == "Skill"
                    ):
                        args = part["input"].get("args") or ""
                        yield "claude", "tool", part["input"].get("skill"), args, time, cwd, path


def codex_events(dirs: list[Path], since: str):
    for path in (HOME / ".codex" / "sessions").glob("*/*/*/*.jsonl"):
        cwd, seen = None, set()
        for item in records(path):
            payload = item.get("payload")
            if not isinstance(payload, dict):
                continue
            if cwd is None and payload.get("cwd"):
                cwd = payload["cwd"]
                if not inside(cwd, dirs):
                    break
            if payload.get("type") not in ("function_call", "custom_tool_call"):
                continue
            time = item.get("timestamp", "")
            text = json.dumps(payload.get("arguments") or payload.get("input") or "")
            for name in set(SKILL_READ_RE.findall(text)) - seen:
                seen.add(name)
                if time >= since:
                    yield "codex", "read", name, "", time, cwd, path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=".", help="logbooks repository root")
    parser.add_argument("--projects-dir", default="projects")
    parser.add_argument("--since", default="", help="ISO date lower bound")
    parser.add_argument("--json", action="store_true", help="emit every event")
    args = parser.parse_args(argv)
    root = root_path(args.root)
    dirs = work_dirs(root, args.projects_dir)
    events = [
        {
            "runtime": runtime,
            "how": how,
            "skill": skill,
            "args": args_text[:200],
            "time": time,
            "cwd": cwd.replace(str(HOME), "~", 1),
            "session": str(path).replace(str(HOME), "~", 1),
        }
        for source in (claude_events(dirs, args.since), codex_events(dirs, args.since))
        for runtime, how, skill, args_text, time, cwd, path in source
        if skill
    ]
    events.sort(key=lambda e: e["time"])
    if args.json:
        print(json.dumps(events, ensure_ascii=False, indent=2))
        return 0
    counts = Counter((e["skill"], e["cwd"]) for e in events)
    for (skill, cwd), n in counts.most_common():
        print(f"{n:4} {skill}  {cwd}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
