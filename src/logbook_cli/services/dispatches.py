"""Dispatch/attempt records in Thinking; no second scheduler or task acceptance."""

import json
from datetime import datetime, timezone

from logbook_cli import execution, records, task_identity
from logbook_cli.document import (
    EXIT_REFUSED,
    EXIT_USAGE,
    LbError,
    require_preflight_clear,
    require_token,
    safe_path,
)
from logbook_cli.lifecycle import get
from logbook_cli.services.closeout import thinking_path
from logbook_cli.services.common import Result, load, save

TRANSITIONS = {
    "prepared": {"sent", "cancelled"},
    "sent": {"acknowledged", "cancelled"},
    "acknowledged": {"returned", "cancelled"},
    "returned": {"closed"},
    "closed": set(),
    "cancelled": set(),
}


def documents(root, log, thinking):
    doc = load(root, log)
    target = load(root, thinking_path(doc, thinking))
    execution_path, execution_data, state = execution.read(doc)
    if state and target.path != execution.project(doc) / state["thinking"]:
        raise LbError("dispatch Thinking differs from execution binding", EXIT_REFUSED)
    target.dependencies = [(doc.path, doc.data)]
    target.state_dependencies = [(doc.path, doc.state_data)]
    if execution_path:
        target.dependencies.append((execution_path, execution_data))
    return doc, target


def read(doc, thinking, dispatch_id=None):
    rows = [
        r
        for _, r in records.read(thinking, "dispatch")
        if r.get("log_id") == records.document_id(doc)
        and records.document_id(doc) is not None
    ]
    ids = [r.get("id") for r in rows]
    if len(ids) != len(set(ids)) or any(
        r.get("status") not in TRANSITIONS for r in rows
    ):
        raise LbError("duplicate dispatch ID or invalid status", EXIT_REFUSED)
    if dispatch_id is None:
        return rows
    matches = [r for r in rows if r.get("id") == dispatch_id]
    if len(matches) != 1:
        raise LbError("missing or ambiguous dispatch", EXIT_REFUSED)
    task_identity.lookup(doc, matches[0]["task_id"])
    return matches[0]


def guard(doc, target, token, advancing, dispatch_id=None, owner=None):
    require_token(target, token)
    require_preflight_clear(doc)
    if advancing:
        execution.require_delegation(doc, dispatch_id, owner)
    if advancing and get(doc)["value"] != "active":
        raise LbError("dispatch advancement requires an active logbook", EXIT_REFUSED)


def show(root, log, thinking, dispatch_id=None):
    doc, target = documents(root, log, thinking)
    return Result(
        {"dispatches": read(doc, target, dispatch_id), "version_token": target.token}
    )


@execution.serialized
def create(root, log, thinking, input_file, token, dry_run):
    doc, target = documents(root, log, thinking)
    guard(doc, target, token, False)
    try:
        data = json.loads(safe_path(doc.root, input_file).read_text())
        keys = {
            "id",
            "task_id",
            "owner",
            "scope",
            "exclusions",
            "inputs",
            "completion",
            "escalation",
        }
        if not isinstance(data, dict) or set(data) != keys:
            raise ValueError("dispatch input requires: " + ", ".join(sorted(keys)))
        for key in keys:
            records.single_line(data[key], key)
    except (ValueError, TypeError) as exc:
        raise LbError(str(exc), EXIT_USAGE) from exc
    guard(doc, target, token, True, data["id"], data["owner"])
    task, _, item = task_identity.lookup(doc, data["task_id"])
    if (
        task.human
        or item["status"] not in {"pending", "active"}
        or not task_identity.snapshot(task, item)["consistent"]
    ):
        raise LbError("dispatch requires a pending/active agent task", EXIT_REFUSED)
    all_rows = [r for _, r in records.read(target, "dispatch")]
    if any(r.get("id") == data["id"] for r in all_rows):
        raise LbError("dispatch ID already exists; inspect before retry", EXIT_REFUSED)
    if any(
        r["task_id"] == data["task_id"] and r["status"] not in {"closed", "cancelled"}
        for r in read(doc, target)
    ):
        raise LbError("task already has an open dispatch", EXIT_REFUSED)
    value = {
        **data,
        "log": str(doc.path.relative_to(doc.root)),
        "log_id": records.document_id(doc),
        "status": "prepared",
        "attempts": [],
        "history": [],
    }
    return save(target, records.put(target, "dispatch", value), dry_run, dispatch=value)


@execution.serialized
def transition(root, log, thinking, dispatch_id, status, basis, token, dry_run):
    doc, target = documents(root, log, thinking)
    old = read(doc, target, dispatch_id)
    guard(
        doc,
        target,
        token,
        status in {"sent", "acknowledged"},
        dispatch_id,
        old["owner"],
    )
    records.single_line(basis, "basis")
    if status not in TRANSITIONS[old["status"]]:
        raise LbError("invalid dispatch transition", EXIT_REFUSED)
    attempts = old["attempts"]
    if status == "returned" and (
        not attempts or any(a["status"] == "started" for a in attempts)
    ):
        raise LbError("return requires terminal attempt records", EXIT_REFUSED)
    if status == "cancelled" and any(a["status"] == "started" for a in attempts):
        raise LbError(
            "record interruption before cancelling dispatch; this command does not stop an agent",
            EXIT_REFUSED,
        )
    event = {
        "from": old["status"],
        "to": status,
        "basis": basis,
        "at": datetime.now(timezone.utc).isoformat(),
    }
    value = {**old, "status": status, "history": [*old["history"], event]}
    return save(
        target,
        records.put(target, "dispatch", value),
        dry_run,
        dispatch=value,
        task_changed=False,
    )


@execution.serialized
def attempt(
    root, log, thinking, dispatch_id, attempt_id, status, basis, token, dry_run
):
    doc, target = documents(root, log, thinking)
    old = read(doc, target, dispatch_id)
    guard(doc, target, token, status == "started", dispatch_id, old["owner"])
    for key, value in (("attempt_id", attempt_id), ("basis", basis)):
        records.single_line(value, key)
    if old["status"] != "acknowledged":
        raise LbError("attempts require an acknowledged dispatch", EXIT_REFUSED)
    attempts = [dict(a) for a in old["attempts"]]
    matches = [a for a in attempts if a["id"] == attempt_id]
    if status == "started":
        if matches or any(a["status"] == "started" for a in attempts):
            raise LbError(
                "attempt already exists or another attempt is running", EXIT_REFUSED
            )
        attempts.append(
            {
                "id": attempt_id,
                "status": status,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "basis": basis,
            }
        )
    else:
        if len(matches) != 1 or matches[0]["status"] != "started":
            raise LbError("only a started attempt can finish", EXIT_REFUSED)
        matches[0].update(
            status=status, basis=basis, ended_at=datetime.now(timezone.utc).isoformat()
        )
    value = {**old, "attempts": attempts}
    return save(
        target,
        records.put(target, "dispatch", value),
        dry_run,
        dispatch=value,
        task_changed=False,
    )
