"""Dispatch-bound runtime identity with live adapter checks."""

import json

from logbook_cli import execution, records
from logbook_cli.adapters import herdr
from logbook_cli.document import EXIT_REFUSED, EXIT_USAGE, LbError, safe_path
from logbook_cli.services import dispatches
from logbook_cli.services.common import Result, save


def binding(doc, target, dispatch_id):
    dispatches.read(doc, target, dispatch_id)
    rows = [
        r
        for _, r in records.read(target, "agent")
        if r.get("id") == dispatch_id
        and r.get("log") == str(doc.path.relative_to(doc.root))
    ]
    if len(rows) != 1:
        raise LbError("missing or ambiguous agent binding", EXIT_REFUSED)
    return rows[0]


@execution.serialized
def bind(root, log, thinking, dispatch_id, input_file, token, dry_run):
    doc, target = dispatches.documents(root, log, thinking)
    dispatches.guard(doc, target, token, False)
    dispatch = dispatches.read(doc, target, dispatch_id)
    if dispatch["status"] in {"closed", "cancelled"}:
        raise LbError("cannot rebind a terminal dispatch", EXIT_REFUSED)
    try:
        item = json.loads(safe_path(doc.root, input_file).read_text())
        keys = {
            "machine",
            "workspace_id",
            "tab_id",
            "pane_id",
            "agent_id",
            "session_id",
            "observed_at",
            "basis",
        }
        if not isinstance(item, dict) or set(item) != keys:
            raise ValueError("binding requires: " + ", ".join(sorted(keys)))
        herdr.validate_binding(item)
    except (ValueError, TypeError) as exc:
        raise LbError(str(exc), EXIT_USAGE) from exc
    value = {
        **item,
        "id": dispatch_id,
        "log": str(doc.path.relative_to(doc.root)),
        "task_id": dispatch["task_id"],
    }
    return save(
        target,
        records.put(target, "agent", value),
        dry_run,
        binding=value,
        live_verified=False,
    )


def inspect(root, log, thinking, dispatch_id, live):
    doc, target = dispatches.documents(root, log, thinking)
    item = binding(doc, target, dispatch_id)
    return Result(
        {
            "binding": item,
            "version_token": target.token,
            **(
                herdr.inspect(item)
                if live
                else {"live_verified": False, "coverage": "saved binding only"}
            ),
        }
    )


def control(
    root,
    log,
    thinking,
    dispatch_id,
    action,
    expected_session,
    expected_observation,
    token,
    dry_run,
    basis=None,
    message_file=None,
    operation_id=None,
    execution_token=None,
):
    doc, target = dispatches.documents(root, log, thinking)
    dispatch = dispatches.read(doc, target, dispatch_id)
    dispatches.guard(doc, target, token, False, dispatch_id, dispatch["owner"])
    if action == "close":
        records.single_line(basis, "basis")
    item = binding(doc, target, dispatch_id)
    if action == "close" and (
        dispatch["status"] not in {"returned", "closed", "cancelled"}
        or any(a["status"] == "started" for a in dispatch["attempts"])
    ):
        raise LbError(
            "close requires handed-back results and no running attempt", EXIT_REFUSED
        )
    message = safe_path(doc.root, message_file).read_text() if message_file else None
    if action == "send" and (not message or not message.strip()):
        raise LbError("send requires a nonempty --message-file", EXIT_USAGE)
    if action == "send":
        from logbook_cli.services import transport

        with execution.writer(doc, dry_run):
            # Reload both documents inside the lock, including Thinking CAS/preflight.
            doc, target = dispatches.documents(root, log, thinking)
            dispatches.guard(doc, target, token, False)
            dispatch = dispatches.read(doc, target, dispatch_id)
            item = binding(doc, target, dispatch_id)
            return transport.send(
                doc,
                target,
                dispatch,
                item,
                message,
                operation_id,
                execution_token,
                expected_session,
                expected_observation,
                dry_run,
            )
    return Result(
        herdr.control(
            item, action, expected_session, expected_observation, message, dry_run
        )
    )
