"""Herdr-specific native session provisioning and owned-pane cleanup."""

import json

from logbook_cli import records
from logbook_cli.adapters import herdr
from logbook_cli.document import EXIT_REFUSED, EXIT_USAGE, LbError, safe_path
from logbook_cli.services import herdr_labels
from logbook_cli.services.common import Result


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
    if (
        not isinstance(scope, dict)
        or not scope.get("running")
        or scope.get("compatible") is False
        or (scope.get("session") or "default") != server
    ):
        raise LbError("server scope mismatch; no fallback allowed", EXIT_REFUSED)
    if action == "open":
        prefix = herdr_labels.prefix(base)
        created = []
        display_policy = None
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
            display_policy = herdr_labels.apply(
                lambda *args: herdr.invoke(
                    machine, *args, mutation=args[1] == "rename"
                ),
                "pane",
                pane_id,
                prefix,
                request["name"],
            )
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
                    "display_policy": display_policy,
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
                    **(
                        {"failure_stage": exc.stage, "display_policy": exc.policy}
                        if isinstance(exc, herdr_labels.LabelFailure)
                        else {"display_policy": display_policy}
                    ),
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
