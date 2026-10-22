"""Journal one send around its external effect; unknown outcomes never auto-retry."""

import copy
import hashlib
import json

from logbook_cli import execution, records
from logbook_cli.adapters import herdr
from logbook_cli.document import EXIT_REFUSED, LbError
from logbook_cli.services.common import Result


def send(
    doc,
    thinking,
    dispatch,
    binding,
    message,
    operation_id,
    token,
    expected_session,
    expected_observation,
    dry_run,
):
    records.single_line(operation_id, "operation_id")
    path, raw, state = execution.read(doc)
    execution.require_token(doc, path, raw, token)
    if state is None:
        # An empty record journals transport only; it asserts no takeover.
        state = execution.initial(doc, thinking)
    if expected_session != binding["session_id"]:
        raise LbError("expected session differs from recipient binding", EXIT_REFUSED)
    # Exclude lifecycle/history and transient observation tokens from package identity.
    package = {
        key: dispatch[key]
        for key in (
            "task_id",
            "owner",
            "scope",
            "exclusions",
            "inputs",
            "completion",
            "escalation",
        )
    }
    request = {
        "dispatch_id": dispatch["id"],
        "recipient": dispatch["owner"],
        "session_id": binding["session_id"],
        "binding_digest": hashlib.sha256(
            json.dumps(
                {
                    key: binding[key]
                    for key in (
                        "machine",
                        "workspace_id",
                        "tab_id",
                        "pane_id",
                        "agent_id",
                        "session_id",
                    )
                },
                sort_keys=True,
            ).encode()
        ).hexdigest(),
        "message_digest": hashlib.sha256(message.encode()).hexdigest(),
        "package_digest": hashlib.sha256(
            json.dumps(package, sort_keys=True).encode()
        ).hexdigest(),
    }
    existing = next(
        (op for op in state["operations"] if op["id"] == operation_id), None
    )
    if existing:
        if existing["request"] != request:
            raise LbError(
                "operation ID already binds another message/package/recipient",
                EXIT_REFUSED,
            )
        if existing["outcome"] == "submitted":
            return Result(
                {
                    "operation": existing,
                    "replayed_record": True,
                    "effect": "no runtime operation",
                    "version_token": token,
                    "runtime_transfer_verified": False,
                }
            )
        raise LbError(
            "operation already recorded; reconcile unknown delivery, or use a new ID only after observed non-delivery",
            EXIT_REFUSED,
        )
    if any(
        op["request"]["dispatch_id"] == dispatch["id"]
        and op["outcome"] != "not_submitted"
        for op in state["operations"]
    ):
        raise LbError(
            "dispatch already has submitted or unknown delivery; changing operation ID cannot resend it",
            EXIT_REFUSED,
        )
    from logbook_cli.lifecycle import get

    if get(doc)["value"] != "active":
        raise LbError("new send requires active Logbook", EXIT_REFUSED)
    execution.require_delegation(doc, dispatch["id"], dispatch["owner"])
    projected = execution.projection(state)
    if projected["takeover"] and projected["reported_owner"] == "unknown":
        raise LbError(
            "ownership is unknown or conflicting; observe a safe boundary before send, not new permission",
            EXIT_REFUSED,
        )
    if projected["handoff"] and projected["handoff"]["receipt"]["status"] in (
        "accepted",
        "unknown",
    ):
        raise LbError(
            "handoff already has accepted or unknown receipt; reconcile without resending",
            EXIT_REFUSED,
        )
    if dispatch["status"] != "prepared":
        raise LbError("new send requires a prepared dispatch", EXIT_REFUSED)
    changed = copy.deepcopy(state)
    intent = {
        "id": operation_id,
        "request": request,
        "outcome": "unknown",
        "receipt": None,
        "provenance": "adapter",
    }
    changed["operations"].append(intent)
    intent_token = None

    def persist_intent():
        nonlocal intent_token
        intent_token = execution.write(doc, state["name"], changed, token, False)[
            "version_token"
        ]

    # The adapter calls persist_intent after live preconditions, before transport.
    result = herdr.control(
        binding,
        "send",
        expected_session,
        expected_observation,
        message,
        dry_run,
        before_mutation=persist_intent,
    )
    if dry_run:
        return Result(result | {"record_saved": False, "version_token": token})
    if intent_token is None:
        raise LbError(
            "adapter did not journal send intent; reconcile runtime before retry",
            EXIT_REFUSED,
        )
    intent.update(outcome="submitted", receipt=result["receipt"])
    try:
        saved = execution.write(doc, state["name"], changed, intent_token, False)
    except (LbError, OSError):
        return Result(
            {
                "operation_id": operation_id,
                "transport_outcome": "submitted",
                "receipt": result["receipt"],
                "record_saved": False,
                "effect": "transport occurred; durable outcome unknown; reconcile without resend",
                "runtime_transfer_verified": False,
            },
            EXIT_REFUSED,
        )
    return Result(
        {
            **result,
            "operation": intent,
            "version_token": saved["version_token"],
            "record_saved": True,
            "runtime_transfer_verified": False,
        }
    )
