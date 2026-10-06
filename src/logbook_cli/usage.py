"""Skills actually invoked in Claude Code and Codex sessions.

Unlike the rest of lb, this reads outside --root: the transcript stores under
~/.claude/projects and ~/.codex/sessions. Only sessions whose working
directory lies inside a logbook's registered local work directory (or the
logbooks repository itself) are reported, so unrelated projects in those
stores are never surfaced.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from logbook_cli.document import context, discover, parse

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
    home = Path.home()
    bases = [home / ".claude", home / ".agents", home / ".codex", Path(cwd) / ".claude"]
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
    for path in (Path.home() / ".claude" / "projects").glob("*/*.jsonl"):
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
    for path in (Path.home() / ".codex" / "sessions").glob("*/*/*/*.jsonl"):
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


def usage(root: Path, projects_dir: str, since: str) -> list[dict]:
    home = Path.home()
    dirs = work_dirs(root, projects_dir)
    events = [
        {
            "runtime": runtime,
            "how": how,
            "skill": skill,
            "args": args_text[:200],
            "time": time,
            "cwd": cwd.replace(str(home), "~", 1),
            "session": str(path).replace(str(home), "~", 1),
        }
        for source in (claude_events(dirs, since), codex_events(dirs, since))
        for runtime, how, skill, args_text, time, cwd, path in source
        if skill
    ]
    return sorted(events, key=lambda e: e["time"])
