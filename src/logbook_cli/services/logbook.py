"""Logbook discovery, inspection, and synchronization."""

import re

from logbook_cli.document import (
    EXIT_ISSUES,
    EXIT_USAGE,
    LbError,
    check,
    context,
    discover,
    parse,
    root_path,
    safe_path,
    stage_state,
    summary_lines,
)
from logbook_cli.format import MARKER_PATTERN
from logbook_cli.services.common import Result, load, save, writable
from logbook_cli.views import render_todo, state_snapshot, todo_snapshot


def list_logs(root: str, projects_dir: str) -> Result:
    base = root_path(root)
    return Result(
        {"logbooks": [str(p.relative_to(base)) for p in discover(base, projects_dir)]}
    )


def inspect(root: str, log: str, view: str = "context") -> Result:
    doc = load(root, log)
    return Result(state_snapshot(doc) if view == "state" else context(doc))


def validate(root: str, log: str | None, all: bool, projects_dir: str) -> Result:
    if not all and not log:
        raise LbError("check requires LOG or --all", EXIT_USAGE)
    if all and log:
        raise LbError("check accepts either LOG or --all, not both", EXIT_USAGE)
    assert all or log is not None
    base = root_path(root)
    paths = discover(base, projects_dir) if all else [safe_path(base, log or "")]
    problems = [issue for path in paths for issue in check(parse(path, base))]
    return Result(
        problems,
        EXIT_ISSUES if any(p["code"] != "LINK_UNVERIFIED" for p in problems) else 0,
    )


def todo(root: str, log: str, dry_run: bool, json: bool) -> Result:
    doc = load(root, log)
    snapshot = todo_snapshot(doc)
    if json:
        return Result(snapshot)
    rendered = render_todo(snapshot)
    if dry_run:
        return Result(snapshot, text=rendered)
    target = doc.path.parent / "TODO.md"
    target.write_text(rendered, encoding="utf-8")
    return Result(snapshot, text=f"TODO.md written: {target}\n")


def sync(root: str, log: str, token: str, dry_run: bool) -> Result:
    doc = writable(root, log, token)
    changed = doc.text
    replacements = []
    changed_stages = 0
    for stage in doc.stages:
        expected = stage_state(stage)
        if stage.is_delivery and expected and stage.emoji != expected:
            old = doc.text[stage.heading_start : stage.heading_end]
            new = re.sub(
                r"^(##\s+)(?:" + MARKER_PATTERN + r"\s+)?", r"\1" + expected + " ", old
            )
            replacements.append((stage.heading_start, stage.heading_end, new))
            changed_stages += 1
    summaries = summary_lines(doc)
    for record in summaries:
        if not record["owned"] or record["target"] == record["raw"]:
            continue
        original = doc.text[record["start"] : record["end"]]
        newline = (
            "\r\n"
            if original.endswith("\r\n")
            else "\n"
            if original.endswith("\n")
            else ""
        )
        replacements.append(
            (record["start"], record["end"], record["target"] + newline)
        )
    for start, end, value in sorted(replacements, reverse=True):
        changed = changed[:start] + value + changed[end:]
    return save(
        doc,
        changed,
        dry_run,
        changed_stages=changed_stages,
        summary_updated=sum(
            1 for r in summaries if r["owned"] and r["target"] != r["raw"]
        ),
        summary_kept_human=sum(1 for r in summaries if not r["owned"]),
    )
