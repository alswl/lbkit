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
        if r.get("id") == dispatch_id and r.get("log_id") == records.document_id(doc)
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
        "log_id": records.document_id(doc),
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


def session_operation(root, input_file, action):
    """Lifecycle without a user-created Dispatch; ownership stays explicit."""
    import re
    from pathlib import Path

    from logbook_cli.document import root_path

    base = root_path(root)
    try:
        request = json.loads(safe_path(base, input_file).read_text())
        if not isinstance(request, dict):
            raise ValueError("object required")
        if action == "open":
            if set(request) != {
                "machine",
                "server",
                "parent_pane",
                "cwd",
                "runtime",
                "name",
            }:
                raise ValueError(
                    "open requires machine, server, parent_pane, cwd, runtime, name"
                )
            for k, v in request.items():
                records.single_line(v, k)
            if not re.fullmatch(
                r"w[0-9A-Za-z]+:p[0-9A-Za-z]+", request["parent_pane"]
            ) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", request["name"]):
                raise ValueError("invalid parent pane or agent name")
            if (
                request["runtime"] not in {"codex", "claude", "pi"}
                or not Path(request["cwd"]).is_absolute()
            ):
                raise ValueError("runtime/cwd unsupported")
            machine, server = request["machine"], request["server"]
        else:
            if set(request) != {"binding", "owned_panes"}:
                raise ValueError(
                    "close-session requires binding and owned_panes from open"
                )
            b = request["binding"]
            herdr.validate_session_binding(b)
            if (
                not isinstance(b, dict)
                or not isinstance(request["owned_panes"], list)
                or b.get("pane_id") not in request["owned_panes"]
            ):
                raise LbError(
                    "pane is outside the explicitly owned resources", EXIT_REFUSED
                )
            machine, server = b["machine"], b["server"]
    except (ValueError, TypeError, KeyError) as exc:
        raise LbError(str(exc), EXIT_USAGE) from exc
    scope = herdr.invoke(machine, "status", "--json").get("server", {})
    if not isinstance(scope, dict) or not scope.get("running") or scope.get("compatible") is False or (scope.get("session") or "default") != server:
        raise LbError("server scope mismatch; no fallback allowed", EXIT_REFUSED)
    if action == "open":
        created = []
        try:
            pane = (
                herdr.invoke(
                    machine,
                    "pane",
                    "split",
                    request["parent_pane"],
                    "--direction",
                    "right",
                    "--cwd",
                    request["cwd"],
                    "--no-focus",
                    mutation=True,
                )
                .get("result", {})
                .get("pane", {})
            )
            pane_id = pane.get("pane_id")
            if not isinstance(pane_id, str) or not pane_id:
                raise LbError("created pane identity unavailable", EXIT_REFUSED)
            created.append(pane_id)
            herdr.invoke(
                machine,
                "agent",
                "start",
                request["name"],
                "--kind",
                request["runtime"],
                "--pane",
                pane_id,
                mutation=True,
            )
            pane = (
                herdr.invoke(machine, "pane", "get", pane_id)
                .get("result", {})
                .get("pane", {})
            )
            agent = (
                herdr.invoke(machine, "agent", "get", pane_id)
                .get("result", {})
                .get("agent", {})
            )
            observed = herdr.binding_observation(
                {"machine": machine, "server": server}, pane, agent
            )
            if (
                observed["binding"]["pane_id"] != pane_id
                or agent.get("agent") != request["runtime"]
                or (
                    agent.get("foreground_cwd")
                    or pane.get("foreground_cwd")
                    or pane.get("cwd")
                )
                != request["cwd"]
            ):
                raise LbError(
                    "started identity or working directory differs", EXIT_REFUSED
                )
            ready = observed["state"] in {"idle", "done"}
            return Result(
                {
                    "status": "ready" if ready else "unknown",
                    **observed,
                    "owned_panes": created,
                },
                code=0 if ready else 1,
            )
        except LbError as exc:
            return Result(
                {
                    "status": "unknown",
                    "owned_panes": created,
                    "reason": exc.message,
                    "retry": "inspect created resources; do not repeat open blindly",
                },
                code=1,
            )
    b = request["binding"]
    pane = (
        herdr.invoke(machine, "pane", "get", b["pane_id"])
        .get("result", {})
        .get("pane", {})
    )
    agent = (
        herdr.invoke(machine, "agent", "get", b["pane_id"])
        .get("result", {})
        .get("agent", {})
    )
    observed = herdr.binding_observation(b, pane, agent)
    if observed["binding"] != b:
        raise LbError("session identity changed; close refused", EXIT_REFUSED)
    try:
        receipt = herdr.invoke(machine, "pane", "close", b["pane_id"], mutation=True)
        inventory = (
            herdr.invoke(machine, "pane", "list", "--workspace", b["workspace_id"])
            .get("result", {})
            .get("panes")
        )
        closed = isinstance(inventory, list) and all(
            p.get("pane_id") != b["pane_id"] for p in inventory
        )
        return Result(
            {
                "status": "closed" if closed else "unknown",
                "binding": b,
                "receipt": receipt,
                "remaining_owned_panes": [] if closed else [b["pane_id"]],
                "process_cleanup": "not independently verified",
            },
            code=0 if closed else 1,
        )
    except LbError as exc:
        return Result(
            {
                "status": "unknown",
                "binding": b,
                "remaining_owned_panes": [b["pane_id"]],
                "reason": exc.message,
            },
            code=1,
        )
