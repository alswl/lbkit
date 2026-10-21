"""Stable task identities and acceptance snapshots, independent of line numbers."""

from __future__ import annotations

import hashlib
import json

from logbook_cli import records
from logbook_cli.document import EXIT_REFUSED, LbError
from logbook_cli.models import Field

TASK_STATES = {
    "pending": " ",
    "active": "/",
    "submitted": "/",
    "accepted": "x",
    "cancelled": "-",
}


def criteria(task):
    fields = [
        (a.kind.value, a.value)
        for a in task.annotations
        if a.kind in {Field.ACCEPTANCE, Field.SOURCE, Field.SKILLS}
    ]
    return hashlib.sha256(
        json.dumps([task.text, fields], ensure_ascii=False).encode()
    ).hexdigest()


def bindings(doc):
    result = {}
    tasks = [t for s in doc.stages for t in s.tasks]
    for index, item in records.read(doc, "task"):
        owners = [
            t
            for t in tasks
            if t.line <= index
            and all(
                not line.strip() or line.startswith((" ", "\t"))
                for line in doc.lines[t.line : index + 1]
            )
        ]
        if (
            len(owners) != 1
            or not isinstance(item.get("id"), str)
            or not item["id"].strip()
        ):
            raise LbError("orphaned or invalid task identity", EXIT_REFUSED)
        if item["id"] in result or any(
            v[0].line == owners[0].line for v in result.values()
        ):
            raise LbError("duplicate task identity", EXIT_REFUSED)
        if item.get("status") not in TASK_STATES:
            raise LbError("invalid task lifecycle", EXIT_REFUSED)
        result[item["id"]] = (owners[0], index, item)
    return result


def lookup(doc, identity):
    item = bindings(doc).get(identity)
    if item is None:
        raise LbError("unknown task ID; use task list or task identify", EXIT_REFUSED)
    return item


def snapshot(task, item):
    submission = item.get("submission")
    return {
        **item,
        "line": task.line,
        "stage": task.stage,
        "text": task.text,
        "human": task.human,
        "blocked": any(a.kind is Field.BLOCKER for a in task.annotations),
        "consistent": TASK_STATES[item["status"]] == task.state,
        "evidence_applicable": bool(
            submission and submission.get("criteria_digest") == criteria(task)
        ),
    }


def replace(doc, index, item):
    nl = "\r\n" if b"\r\n" in doc.data else "\n"
    return (
        doc.text[: doc.offsets[index]]
        + "    "
        + records.encode("task", item)
        + nl
        + doc.text[doc.offsets[index] + len(doc.lines[index]) :]
    )


def acceptance_issues(doc):
    """Detect stale recorded acceptance without rewriting human task content."""
    issues = []
    for identity, (task, _, item) in bindings(doc).items():
        view = snapshot(task, item)
        if not view["consistent"]:
            issues.append(identity + ": checkbox and lifecycle disagree")
        elif (
            item["status"] == "accepted"
            and item.get("submission")
            and not view["evidence_applicable"]
        ):
            issues.append(identity + ": accepted evidence no longer applies")
    return issues
