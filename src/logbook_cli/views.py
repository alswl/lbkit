"""Read-only human and machine views of a parsed logbook."""

from __future__ import annotations

from logbook_cli.document import (
    Document,
    context,
    stage_state,
    summary_derived,
    summary_lines,
)
from logbook_cli.models import StageStatus, derive_stage_status


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
