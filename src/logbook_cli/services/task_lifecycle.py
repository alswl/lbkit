"""Single-logbook semantic task transitions; execution receipt is not acceptance."""

import json
import re
import uuid
from datetime import datetime, timezone

from logbook_cli import records
from logbook_cli import task_identity as identity
from logbook_cli.document import (
    EXIT_REFUSED,
    EXIT_USAGE,
    LbError,
    find_task,
    parse_text,
    safe_path,
)
from logbook_cli.edit import resolve_task
from logbook_cli.services.common import Result, load, save, writable


def identify(root, log, stage, task, task_id, token, dry_run):
    doc = writable(root, log, token)
    records.read(doc, "task", require_closed=True)
    target = find_task(doc, stage, task)
    known = identity.bindings(doc)
    existing = [r for t, _, r in known.values() if t.line == target.line]
    if existing:
        if task_id and existing[0]["id"] != task_id:
            raise LbError("task already has another ID", EXIT_REFUSED)
        return save(doc, doc.text, dry_run, task_id=existing[0]["id"])
    task_id = task_id or "task-" + uuid.uuid4().hex[:12]
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", task_id) or task_id in known:
        raise LbError(
            "task ID must be unique, 1-64 letters/digits/_/-, starting with a letter",
            EXIT_USAGE,
        )
    state = {" ": "pending", "/": "active", "x": "accepted", "-": "cancelled"}[
        target.state
    ]
    item = {
        "id": task_id,
        "status": state,
        "basis": "identity registration; historical evidence remains unknown",
    }
    nl = "\r\n" if b"\r\n" in doc.data else "\n"
    prefix = "" if doc.text[: target.end].endswith("\n") else nl
    changed = (
        doc.text[: target.end]
        + prefix
        + "    "
        + records.encode("task", item)
        + nl
        + doc.text[target.end :]
    )
    return save(doc, changed, dry_run, task_id=task_id)


def show(root, log, task_id):
    doc = load(root, log)
    task, _, item = identity.lookup(doc, task_id)
    return Result({"task": identity.snapshot(task, item), "version_token": doc.token})


def transition(
    root, log, task_id, action, basis, token, dry_run, input_file=None, candidate=None
):
    doc = writable(root, log, token)
    records.read(doc, "task", require_closed=True)
    task, index, old = identity.lookup(doc, task_id)
    records.single_line(basis, "basis")
    view = identity.snapshot(task, old)
    if not view["consistent"]:
        raise LbError(
            "task metadata and checkbox disagree; reconcile human edits first",
            EXIT_REFUSED,
        )
    if task.human and not (action == "start" and old["status"] == "pending"):
        raise LbError("human-owned task transitions are protected", EXIT_REFUSED)
    transitions = {
        "start": ({"pending"}, "active"),
        "record-result": ({"active", "submitted"}, "submitted"),
        "accept": ({"submitted"}, "accepted"),
        "cancel": ({"pending", "active", "submitted"}, "cancelled"),
        "reopen": ({"submitted", "accepted", "cancelled"}, "active"),
    }
    allowed, status = transitions[action]
    if old["status"] not in allowed:
        raise LbError(f"cannot {action} a {old['status']} task", EXIT_REFUSED)
    item = {
        **old,
        "status": status,
        "basis": basis,
        "at": datetime.now(timezone.utc).isoformat(),
    }
    if action == "record-result":
        try:
            data = json.loads(safe_path(doc.root, input_file).read_text())
            if not isinstance(data, dict) or set(data) != {"candidate", "evidence"}:
                raise ValueError(
                    'result requires {"candidate":"identity", "evidence":["reference"]}'
                )
            records.single_line(data["candidate"], "candidate")
            if not isinstance(data["evidence"], list) or not data["evidence"]:
                raise ValueError("evidence must be a nonempty reference array")
            for ref in data["evidence"]:
                records.single_line(ref, "evidence")
        except (ValueError, TypeError) as exc:
            raise LbError(str(exc), EXIT_USAGE) from exc
        item["submission"] = {**data, "criteria_digest": identity.criteria(task)}
    if action == "accept":
        if not view["evidence_applicable"] or candidate != old.get(
            "submission", {}
        ).get("candidate"):
            raise LbError(
                "acceptance requires the current submitted candidate and applicable evidence",
                EXIT_REFUSED,
            )
        item["acceptance"] = {"candidate": candidate, "basis": basis}
    if action == "reopen":
        item.pop("acceptance", None)
        if task.resolution:
            item["previous_resolution"] = task.resolution
    changed = identity.replace(doc, index, item)
    if action == "cancel":
        changed = changed[: task.state_at] + "-" + changed[task.state_at + 1 :]
        revised = parse_text(changed.encode(), doc.path, doc.root)
        target, _, _ = identity.lookup(revised, task_id)
        changed = resolve_task(
            revised, target, "human-cancelled", basis, "Cancelled by explicit decision."
        )
    else:
        changed = (
            changed[: task.state_at]
            + identity.TASK_STATES[status]
            + changed[task.state_at + 1 :]
        )
    if action == "reopen" and task.resolution:
        revised = parse_text(changed.encode(), doc.path, doc.root)
        target, _, _ = identity.lookup(revised, task_id)
        from logbook_cli.models import Field

        for a in reversed(target.annotations):
            if a.kind is Field.RESOLUTION:
                at = revised.offsets[a.line - 1]
                changed = changed[:at] + changed[at + len(revised.lines[a.line - 1]) :]
    return save(
        doc,
        changed,
        dry_run,
        task_id=task_id,
        status=status,
        effect="task transition only; no dispatch or business execution",
    )
