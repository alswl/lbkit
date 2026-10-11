"""Read-only human and machine views of a parsed logbook."""

from __future__ import annotations

import re
from pathlib import Path

from logbook_cli.document import (
    Document,
    Task,
    context,
    parse,
    stage_state,
    summary_derived,
    summary_lines,
    visible_lines,
)
from logbook_cli.format import ALARM_MARKER, HUMAN_MARKER
from logbook_cli.models import StageStatus, derive_stage_status

TASK_BLOCK_STOP = re.compile(r"^(?:#{1,2} |[-*+] \[[^]]+\] )")


def visible_map(doc: Document) -> dict[int, str | None]:
    """Index -> visible prefix (or None when the line hides in fence/comment)."""
    return {index: prefix for index, prefix in visible_lines(doc.lines)}


def task_block(
    doc: Document, task: Task, visibility: dict[int, str | None] | None = None
) -> list[str]:
    """Visible sub-lines belonging to one top-level task, for marker scans."""
    if visibility is None:
        visibility = visible_map(doc)
    block: list[str] = []
    index = task.line  # zero-based index just past the task's first line
    while index < len(doc.lines):
        visible = visibility.get(index)  # type: ignore[arg-type]
        if visible is None:
            index += 1
            continue
        if TASK_BLOCK_STOP.match(visible) and not visible.startswith((" ", "\t")):
            break
        block.append(visible.rstrip("\r\n"))
        index += 1
    return block


def todo_snapshot(doc: Document) -> dict:
    next_task = context(doc)["next_task"]
    visibility = visible_map(doc)
    items = []
    for stage in doc.stages:
        if not stage.is_delivery:
            continue
        for task in stage.tasks:
            blockers = ([task.text] if ALARM_MARKER in task.text else []) + [
                b for b in task_block(doc, task, visibility) if ALARM_MARKER in b
            ]
            items.append(
                {
                    "stage": stage.title,
                    "line": task.line,
                    "state": task.state,
                    "human": task.human,
                    "settled": task.settled,
                    "resolution": task.resolution,
                    "text": task.text,
                    "blockers": blockers,
                }
            )
    return {
        "logbook": str(doc.path.relative_to(doc.root)),
        "language": doc.locale,
        "next_task": next_task,
        "alarms": [i for i in items if i["blockers"]],
        "human_pending": [i for i in items if i["human"] and not i["settled"]],
        "doing": [i for i in items if i["state"] == "/"],
        "todo": [i for i in items if i["state"] == " "],
        "skipped": [i for i in items if i["state"] == "-" and not i["settled"]],
        "resolved": [i for i in items if i["resolution"]],
    }


def render_todo(snapshot: dict) -> str:
    from logbook_cli.messages import TODO

    words = TODO[snapshot.get("language", "zh")]
    rel = snapshot["logbook"]
    out = [
        words["generated"].format(rel=rel),
        "",
        words["title"],
        "",
        words["source"].format(rel=rel),
        "",
    ]

    def location(item):
        return words["location"].format(stage=item["stage"], line=item["line"])

    if snapshot["alarms"]:
        out.extend(["## " + ALARM_MARKER + " " + words["alarm"], ""])
        for item in snapshot["alarms"]:
            out.append(f"- **{item['text']}**" + location(item))
            out.extend(
                "  - " + b.strip() for b in item["blockers"] if b != item["text"]
            )
        out.append("")
    if snapshot["human_pending"]:
        out.extend(["## " + HUMAN_MARKER + " " + words["human"], ""])
        for item in snapshot["human_pending"]:
            state = {" ": "[ ]", "/": "[/]"}.get(item["state"], "")
            out.append("- " + item["text"] + location(item) + state)
        out.append("")
    out.extend(["## " + words["next"], ""])
    nxt = snapshot["next_task"]
    if nxt and nxt.get("text"):
        owner = words["human_owner"] if nxt.get("human") else "Agent"
        out.append(
            "- "
            + nxt["text"]
            + words["owner_location"].format(
                stage=nxt.get("stage", ""), line=nxt.get("line", 0), owner=owner
            )
        )
    else:
        key = (
            "skipped"
            if snapshot["skipped"]
            else "settled"
            if snapshot["resolved"]
            else "done"
        )
        out.append("- " + words[key])
    out.append("")
    if snapshot["doing"]:
        out.extend(["## " + words["doing"], ""])
        out.extend("- " + item["text"] + location(item) for item in snapshot["doing"])
        out.append("")
    out.append(words["footer"])
    return "\n".join(out) + "\n"


def refresh_todo(doc: Document) -> Path | None:
    """Regenerate TODO.md beside the logbook when one already exists.

    Re-parses from disk so post-write state is what gets rendered.
    """
    target = doc.path.parent / "TODO.md"
    if not target.exists():
        return None
    fresh = parse(doc.path, doc.root)
    target.write_text(render_todo(todo_snapshot(fresh)), encoding="utf-8")
    return target


def state_snapshot(doc: Document) -> dict:
    delivery = {s.title: derive_stage_status(s) for s in doc.stages if s.is_delivery}
    records = summary_lines(doc)
    return {
        "path": str(doc.path.relative_to(doc.root)),
        "version_token": doc.token,
        "summary": summary_derived(doc),
        "overall": {
            "delivery_stages": len(delivery),
            "done": sum(1 for v in delivery.values() if v is StageStatus.SETTLED),
            "in_flight": sum(
                1 for v in delivery.values() if v is StageStatus.IN_PROGRESS
            ),
            "not_started": sum(
                1 for v in delivery.values() if v is StageStatus.NOT_STARTED
            ),
            "preflight_clear": not doc.preflight,
        },
        "preflight_blockers": doc.preflight,
        "next_task": context(doc)["next_task"],
        "stages": [
            {
                "title": s.title,
                "line": s.line,
                "emoji": s.emoji,
                "derived_emoji": stage_state(s),
                "delivery": s.is_delivery,
                "tasks": {
                    "todo": sum(1 for t in s.tasks if t.state == " "),
                    "doing": sum(1 for t in s.tasks if t.state == "/"),
                    "done": sum(1 for t in s.tasks if t.state == "x"),
                    "skipped": sum(1 for t in s.tasks if t.state == "-"),
                    "human_pending": sum(
                        1 for t in s.tasks if t.human and not t.settled
                    ),
                },
            }
            for s in doc.stages
        ],
        "page_status_lines": [
            {"line": r["line"], "owned": r["owned"]} for r in records
        ],
    }


def task_rows(
    doc: Document,
    *,
    stage: str | None = None,
    state: str | None = None,
    human: bool = False,
) -> list[dict]:
    """Return schedulable tasks with stable source locations."""
    path = str(doc.path.relative_to(doc.root))
    return [
        {
            "path": path,
            "stage": section.title,
            "line": task.line,
            "state": task.state,
            "text": task.text,
            "human": task.human,
            "settled": task.settled,
            "resolution": task.resolution,
            "repositories": task.repositories,
            "preflight": task.preflight_blocker,
        }
        for section in doc.stages
        if section.is_delivery and (stage is None or section.title == stage)
        for task in section.tasks
        if (state is None or task.state == state) and (not human or task.human)
    ]
