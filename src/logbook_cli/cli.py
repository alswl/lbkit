"""Small, dependency-free reader and guarded editor for Logbooks Markdown."""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

# Direct script execution sets sys.path to scripts/, while test imports use the
# repository root. Keep both entry forms on the same package import path.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from logbook_cli.document import (
    EXIT_ISSUES,
    EXIT_PATH,
    EXIT_REFUSED,
    EXIT_USAGE,
    Document,
    LbError,
    check,
    context,
    discover,
    find_task,
    parse,
    require_preflight_clear,
    require_token,
    root_path,
    safe_path,
    stage_state,
    summary_lines,
)
from logbook_cli.edit import NOTE_KINDS, add_task, append_note, require_valid_candidate
from logbook_cli.views import (
    refresh_todo,
    render_todo,
    state_snapshot,
    task_rows,
    todo_snapshot,
)


def err(message: str, code: int = EXIT_PATH) -> None:
    print(f"lb: {message}", file=sys.stderr)
    raise SystemExit(code)


def write_bytes(doc: Document, changed: bytes, dry_run: bool) -> None:
    if dry_run:
        return

    def current_path() -> Path:
        return safe_path(doc.root, str(doc.path))

    if current_path().read_bytes() != doc.data:
        raise LbError(
            "file changed since it was read; reread context before writing",
            EXIT_REFUSED,
        )
    fd, temporary = tempfile.mkstemp(prefix=".lb-", dir=doc.path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(changed)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, doc.path.stat().st_mode)
        # Recheck immediately before replace: fsync and metadata work can be
        # slow enough for another editor to change or replace the source.
        if current_path().read_bytes() != doc.data:
            raise LbError(
                "file changed during write preparation; reread context before writing",
                EXIT_REFUSED,
            )
        os.replace(temporary, doc.path)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def emit(value: object, as_json: bool) -> None:
    if as_json:
        print(json.dumps(value, ensure_ascii=False, indent=2))
    elif isinstance(value, list):
        for item in value:
            print(f"{item['path']}:{item['line']}: {item['code']}: {item['message']}")
    else:
        print(json.dumps(value, ensure_ascii=False, indent=2))


def unified_diff(doc: Document, changed: str) -> str:
    path = str(doc.path.relative_to(doc.root))
    return "".join(
        difflib.unified_diff(
            doc.text.splitlines(keepends=True),
            changed.splitlines(keepends=True),
            fromfile=path,
            tofile=path,
        )
    )


def emit_write(
    doc: Document, changed: str, dry_run: bool, as_json: bool, **details: object
) -> None:
    value = {
        "path": str(doc.path.relative_to(doc.root)),
        "dry_run": dry_run,
        "issues_introduced": [],
        **details,
    }
    if dry_run:
        value["diff"] = unified_diff(doc, changed)
    if as_json:
        print(json.dumps(value, ensure_ascii=False, indent=2))
    elif dry_run:
        print(value["diff"], end="")
    else:
        print(json.dumps(value, ensure_ascii=False, indent=2))


def cmd_todo(args: argparse.Namespace) -> int:
    doc = load(args)
    snapshot = todo_snapshot(doc)
    if args.json:
        emit(snapshot, args.json)
        return 0
    target = doc.path.parent / "TODO.md"
    if args.dry_run:
        print(render_todo(snapshot), end="")
        return 0
    target.write_text(render_todo(snapshot), encoding="utf-8")
    print(f"TODO.md written: {target}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    root = root_path(args.root)
    paths = [str(p.relative_to(root)) for p in discover(root, args.projects_dir)]
    emit(
        {"logbooks": paths}
        if args.json
        else [
            {"path": p, "line": 1, "code": "LOGBOOK", "message": "discovered"}
            for p in paths
        ],
        args.json,
    )
    return 0


def load(args: argparse.Namespace, name: str = "log") -> Document:
    root = root_path(args.root)
    return parse(safe_path(root, getattr(args, name)), root)


def cmd_context(args: argparse.Namespace) -> int:
    emit(context(load(args)), args.json)
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    root = root_path(args.root)
    docs = (
        [parse(p, root) for p in discover(root, args.projects_dir)]
        if args.all
        else [parse(safe_path(root, args.log), root)]
    )
    problems = [problem for doc in docs for problem in check(doc)]
    emit(problems, args.json)
    return EXIT_ISSUES if any(p["code"] != "LINK_UNVERIFIED" for p in problems) else 0


def cmd_sync(args: argparse.Namespace) -> int:
    doc = load(args)
    require_token(doc, args.token)
    require_preflight_clear(doc)
    changed = doc.text
    replacements = []
    changed_stages = 0
    for stage in doc.stages:
        expected = stage_state(stage)
        if stage.is_delivery and expected and stage.emoji != expected:
            old = doc.text[stage.heading_start : stage.heading_end]
            new = re.sub(
                r"^(##\s+)(?:(?:🛫|🚧|✅|⚠️?)\s+)?", r"\1" + expected + " ", old
            )
            replacements.append((stage.heading_start, stage.heading_end, new))
            changed_stages += 1
    summary_updates = summary_lines(doc)
    for record in summary_updates:
        if not record["owned"] or record["target"] == record["raw"]:
            continue
        original = doc.text[record["start"] : record["end"]]
        newline = (
            "\r\n"
            if original.endswith("\r\n")
            else ("\n" if original.endswith("\n") else "")
        )
        replacements.append(
            (record["start"], record["end"], record["target"] + newline)
        )
    for start, end, value in sorted(
        replacements, key=lambda item: item[0], reverse=True
    ):
        changed = changed[:start] + value + changed[end:]
    require_valid_candidate(doc, changed)
    write_bytes(doc, changed.encode("utf-8"), args.dry_run)
    if not args.dry_run:
        refresh_todo(doc)
    emit_write(
        doc,
        changed,
        args.dry_run,
        args.json,
        changed_stages=changed_stages,
        summary_updated=sum(
            1 for r in summary_updates if r["owned"] and r["target"] != r["raw"]
        ),
        summary_kept_human=sum(1 for r in summary_updates if not r["owned"]),
    )
    return 0


def cmd_state(args: argparse.Namespace) -> int:
    emit(state_snapshot(load(args)), args.json)
    return 0


def cmd_task_update(args: argparse.Namespace) -> int:
    doc = load(args)
    require_token(doc, args.token)
    require_preflight_clear(doc)
    task = find_task(doc, args.stage, args.task)
    if task.human:
        raise LbError(
            "refusing to change a human-owned task checkbox; only the human owner may edit it",
            EXIT_REFUSED,
        )
    if args.status not in (" ", "/", "x", "-"):
        raise LbError("--status must be one of: space, /, x, -", EXIT_USAGE)
    changed = doc.text[: task.state_at] + args.status + doc.text[task.state_at + 1 :]
    require_valid_candidate(doc, changed)
    write_bytes(doc, changed.encode("utf-8"), args.dry_run)
    if not args.dry_run:
        refresh_todo(doc)
    emit_write(doc, changed, args.dry_run, args.json, line=task.line)
    return 0


def cmd_task_artifact(args: argparse.Namespace) -> int:
    doc = load(args)
    require_token(doc, args.token)
    require_preflight_clear(doc)
    task = find_task(doc, args.stage, args.task)
    changed, line = append_note(doc, task, args.artifact)
    require_valid_candidate(doc, changed)
    write_bytes(doc, changed.encode("utf-8"), args.dry_run)
    if not args.dry_run:
        refresh_todo(doc)
    emit_write(doc, changed, args.dry_run, args.json, line=line)
    return 0


def cmd_task_note(args: argparse.Namespace) -> int:
    doc = load(args)
    require_token(doc, args.token)
    require_preflight_clear(doc)
    task = find_task(doc, args.stage, args.task)
    changed, line = append_note(doc, task, args.text, args.kind)
    require_valid_candidate(doc, changed)
    write_bytes(doc, changed.encode("utf-8"), args.dry_run)
    if not args.dry_run:
        refresh_todo(doc)
    emit_write(doc, changed, args.dry_run, args.json, line=line)
    return 0


def cmd_task_add(args: argparse.Namespace) -> int:
    doc = load(args)
    require_token(doc, args.token)
    require_preflight_clear(doc)
    changed, line = add_task(doc, args.stage, args.text, args.before_line)
    require_valid_candidate(doc, changed)
    write_bytes(doc, changed.encode("utf-8"), args.dry_run)
    if not args.dry_run:
        refresh_todo(doc)
    emit_write(doc, changed, args.dry_run, args.json, line=line)
    return 0


def cmd_task_list(args: argparse.Namespace) -> int:
    root = root_path(args.root)
    paths = [safe_path(root, args.log)] if args.log else discover(root, args.projects_dir)
    states = {"todo": " ", "in-progress": "/", "done": "x", "skipped": "-"}
    state = states.get(args.status) if args.status else None
    rows = [
        row
        for path in paths
        for row in task_rows(
            parse(path, root), stage=args.stage, state=state, human=args.human
        )
    ]
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        for row in rows:
            print(f"{row['path']}:{row['line']}: [{row['state']}] {row['text']}")
    return 0


def cmd_task_next(args: argparse.Namespace) -> int:
    task = context(load(args))["next_task"]
    if args.json:
        print(json.dumps(task, ensure_ascii=False, indent=2))
    elif task is not None:
        print(f"{task['stage']}:{task['line']}: [{task['state']}] {task['text']}")
    return 0


def add_root_option(
    command: argparse.ArgumentParser, *, top_level: bool = False
) -> None:
    # Child defaults must not overwrite a root supplied before the subcommand.
    command.add_argument(
        "--root",
        default="." if top_level else argparse.SUPPRESS,
        metavar="DIR",
        help="repository root; paths stay beneath it (default: current directory)",
    )


def add_projects_dir_option(command: argparse.ArgumentParser) -> None:
    command.add_argument(
        "--projects-dir",
        default="projects",
        metavar="PATH",
        help="project collection relative to --root (default: projects)",
    )


def add_output_option(command: argparse.ArgumentParser) -> None:
    command.add_argument(
        "--json", action="store_true", help="emit machine-readable JSON"
    )


def add_write_options(command: argparse.ArgumentParser) -> None:
    command.add_argument("--token", required=True, help="version_token from context")
    command.add_argument(
        "--dry-run", action="store_true", help="preview the diff without writing"
    )


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="lb",
        description=__doc__,
        epilog="Example: bin/lb context projects/demo/logbook.md --json",
    )
    add_root_option(p, top_level=True)
    sub = p.add_subparsers(dest="command", required=True)
    q = sub.add_parser("list", help="list project logbooks")
    add_root_option(q)
    add_projects_dir_option(q)
    add_output_option(q)
    q.set_defaults(func=cmd_list)
    for name in ("context", "show", "next"):
        q = sub.add_parser(name, help="show context, version token and next task")
        add_root_option(q)
        q.add_argument("log", help="logbook path relative to --root")
        add_output_option(q)
        q.set_defaults(func=cmd_context)
    q = sub.add_parser("check", help="check one logbook or all project logbooks")
    add_root_option(q)
    add_projects_dir_option(q)
    q.add_argument("log", nargs="?", help="logbook path relative to --root")
    q.add_argument("--all", action="store_true", help="check all project logbooks")
    add_output_option(q)
    q.set_defaults(func=cmd_check)
    q = sub.add_parser(
        "todo", help="regenerate the human-view TODO.md beside the logbook"
    )
    add_root_option(q)
    q.add_argument("log", help="logbook path relative to --root")
    q.add_argument(
        "--dry-run",
        action="store_true",
        help="print the TODO.md content without writing",
    )
    add_output_option(q)
    q.set_defaults(func=cmd_todo)
    q = sub.add_parser("state", help="structured state snapshot with derived summary")
    add_root_option(q)
    q.add_argument("log", help="logbook path relative to --root")
    add_output_option(q)
    q.set_defaults(func=cmd_state)
    q = sub.add_parser(
        "sync", help="synchronize stage status emoji and owned 状态 summary lines"
    )
    add_root_option(q)
    q.add_argument("log", help="logbook path relative to --root")
    add_write_options(q)
    add_output_option(q)
    q.set_defaults(func=cmd_sync)
    q = sub.add_parser("task", help="add, update, or annotate a task")
    add_root_option(q)
    task_sub = q.add_subparsers(dest="task_command", required=True)
    command = task_sub.add_parser("list", help="filter tasks in one or all logbooks")
    add_root_option(command)
    add_projects_dir_option(command)
    command.add_argument(
        "log", nargs="?", help="optional logbook path relative to --root"
    )
    command.add_argument("--stage", help="exact delivery stage title")
    command.add_argument(
        "--status",
        choices=("todo", "in-progress", "done", "skipped"),
        help="filter by checkbox state",
    )
    command.add_argument(
        "--human", action="store_true", help="show human-owned tasks only"
    )
    add_output_option(command)
    command.set_defaults(func=cmd_task_list)
    command = task_sub.add_parser("next", help="show the next delivery task")
    add_root_option(command)
    command.add_argument("log", help="logbook path relative to --root")
    add_output_option(command)
    command.set_defaults(func=cmd_task_next)
    command = task_sub.add_parser("add", help="add one approved unchecked task")
    add_root_option(command)
    command.add_argument("log", help="logbook path relative to --root")
    command.add_argument("--stage", required=True, help="exact delivery stage title")
    command.add_argument(
        "--text", required=True, help="approved task text without checkbox"
    )
    command.add_argument(
        "--before-line", type=int, help="insert before this task line in the stage"
    )
    add_write_options(command)
    add_output_option(command)
    command.set_defaults(func=cmd_task_add)
    for name, func, description in (
        ("update", cmd_task_update, "update a task checkbox"),
        ("artifact", cmd_task_artifact, "append an artifact to an Agent task"),
        ("note", cmd_task_note, "append a short note to an Agent task"),
    ):
        command = task_sub.add_parser(name, help=description, description=description)
        add_root_option(command)
        command.add_argument("log", help="logbook path relative to --root")
        command.add_argument(
            "--stage", required=True, help="exact stage title without status emoji"
        )
        command.add_argument("--task", required=True, help="exact task text")
        add_write_options(command)
        add_output_option(command)
        command.set_defaults(func=func)
        if name == "update":
            command.add_argument(
                "--status", required=True, help="checkbox state: ' ', '/', 'x' or '-'"
            )
        elif name == "artifact":
            command.add_argument(
                "--artifact",
                required=True,
                help="single-line artifact description and location",
            )
        else:
            command.add_argument("--text", required=True, help="one-line note text")
            command.add_argument(
                "--kind",
                choices=NOTE_KINDS,
                help="optional note prefix: 产物, 阻塞, 状态 or 交接",
            )
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "check" and not args.all and not args.log:
        err("check requires LOG or --all", EXIT_USAGE)
    if args.command == "check" and args.all and args.log:
        err("check accepts either LOG or --all, not both", EXIT_USAGE)
    try:
        return args.func(args)
    except LbError as exc:
        err(exc.message, exc.code)
    except OSError as exc:
        err(f"I/O error: {exc}", EXIT_PATH)


if __name__ == "__main__":
    raise SystemExit(main())
