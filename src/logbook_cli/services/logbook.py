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
from logbook_cli.services.common import Result, load, save
from logbook_cli.views import state_snapshot


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


def sync(root: str, log: str, token: str, dry_run: bool) -> Result:
    doc = load(root, log)
    from logbook_cli.document import require_preflight_clear, require_token

    require_token(doc, token)
    require_preflight_clear(doc)
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
    from logbook_cli.lifecycle import get

    managed = get(doc)["managed"]
    summaries = summary_lines(doc)
    for record in [] if managed else summaries:
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
    from logbook_cli.document import parse_text
    from logbook_cli.lifecycle import get, render

    if (
        get(doc)["managed"]
        or not doc.status_lines
        or any(
            r["raw"].startswith(("> 状态：❔ ", "> Status: ❔ "))
            for r in doc.status_lines
        )
    ):
        changed = render(parse_text(changed.encode(), doc.path, doc.root))
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
