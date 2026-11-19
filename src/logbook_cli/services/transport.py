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
        if {k: v for k, v in existing["request"].items() if k != "task_id"} != request:
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
    from logbook_cli import unified
    from logbook_cli.repository import require_synced
    from logbook_cli.services.readiness import require_ready

    task_id = dispatch["task_id"]
    request["task_id"] = task_id

    def check_readiness():
        current, _ = require_synced(doc.root, doc.path, task_id)
        if current.data != doc.data or thinking.path.read_bytes() != thinking.data:
            raise LbError("dispatch documents changed before send", EXIT_REFUSED)
        _, envelope = unified.locate(doc.root, doc.path, required=True)
        task_send_guard(envelope["execution"], task_id, operation_id, request)
        require_ready(current, envelope, task_id, dispatch["owner"])

    check_readiness()
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
        check_readiness()
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


def task_send_guard(ex, task_id, operation_id, request):
    existing = ex["operations"].get(operation_id)
    if existing:
        if existing["request"] != request:
            raise LbError("operation ID binds another request", EXIT_REFUSED)
        if existing["outcome"] == "submitted":
            return existing
        raise LbError(
            "operation already recorded; reconcile without resend", EXIT_REFUSED
        )
    if any(op["outcome"] == "unknown" for op in ex["operations"].values()):
        raise LbError("unknown delivery blocks further delegation", EXIT_REFUSED)
    delivery_started(ex, task_id, request)
    return None


def delivery_started(ex, task_id, request):
    """Establish first action separately from transport and protect replay."""
    outcomes = {
        fact["operation_id"]: fact["outcome"]
        for fact in ex.get("facts", ())
        if fact["kind"] == "business-action"
    }
    started = False
    for operation_id, op in ex["operations"].items():
        prior = op["request"]
        if prior.get("task_id") != task_id or op["outcome"] != "submitted":
            continue
        if op.get("provenance") == "takeover":
            raise LbError("Captain already started this Task", EXIT_REFUSED)
        outcome = outcomes.get(operation_id)
        if outcome is None:
            raise LbError(
                "Submitted delivery has no business-action outcome; reconcile first",
                EXIT_REFUSED,
            )
        if outcome == "started":
            if prior == request:
                raise LbError("Use the original operation ID to replay", EXIT_REFUSED)
            started |= prior.get("binding_id") == request.get("binding_id")
    return started


def send_task(
    root,
    log,
    task_id,
    binding_id,
    operation_id,
    execution_token,
    expected_session,
    expected_observation,
    message_file,
    dry_run=False,
):
    from logbook_cli import observation, unified
    from logbook_cli.document import safe_path
    from logbook_cli.repository import require_synced
    from logbook_cli.services.readiness import require_ready
    from logbook_cli.services.task_coordination import native_binding
    from logbook_cli.task_identity import dependencies, lookup

    records.single_line(operation_id, "operation_id")
    doc, task = require_synced(root, log, task_id)
    message = safe_path(doc.root, message_file).read_text()
    if not message.strip():
        raise LbError("send requires nonempty message", EXIT_REFUSED)
    with unified.writer(doc.root, doc.path, dry_run):
        doc, task = require_synced(root, log, task_id)
        path, envelope = unified.locate(doc.root, doc.path, required=True)
        if unified.section_token(envelope, "execution") != execution_token:
            raise LbError("execution version conflict", EXIT_REFUSED)
        ex = envelope["execution"]
        runtime = ex["tasks"].get(task_id, {})
        binding = runtime.get("execution_bindings", {}).get(binding_id)
        if binding is None:
            raise LbError("Task binding not found", EXIT_REFUSED)
        native = native_binding(binding)
        if expected_session != native["session_id"]:
            raise LbError("expected session differs", EXIT_REFUSED)
        request = {
            "task_id": task_id,
            "binding_id": binding_id,
            "run_id": envelope["identity"]["run_id"],
            "recipient": binding["subject"]["subject_id"],
            "session_id": binding["session_id"],
            "binding_digest": unified.digest(binding),
            "message_digest": hashlib.sha256(message.encode()).hexdigest(),
        }
        existing = task_send_guard(ex, task_id, operation_id, request)
        if existing:
            return Result(
                {
                    "operation": existing,
                    "replayed_record": True,
                    "effect": "no runtime operation",
                }
            )
        if runtime.get("current_binding_id") != binding_id:
            raise LbError("send requires current Task binding", EXIT_REFUSED)
        if (
            task.human
            or binding["subject"]["kind"] != "agent"
            or task.effective_state not in {"pending", "active"}
        ):
            raise LbError(
                "Task cannot be delegated in current state/ownership", EXIT_REFUSED
            )
        for dep in dependencies(task):
            if lookup(doc, dep)[0].effective_state != "done":
                raise LbError("hard dependency is not done: " + dep, EXIT_REFUSED)
        from logbook_cli.document import require_preflight_clear
        from logbook_cli.lifecycle import get

        require_preflight_clear(doc)
        if get(doc)["value"] != "active":
            raise LbError("new send requires active Logbook", EXIT_REFUSED)
        execution.require_delegation(doc, task_id, binding["subject"]["subject_id"])
        if not delivery_started(ex, task_id, request):
            require_ready(doc, envelope, task_id, binding["subject"]["subject_id"])
    intent_saved = False

    def persist():
        nonlocal intent_saved
        with unified.writer(doc.root, doc.path):
            current, _ = require_synced(root, log, task_id)
            if current.data != doc.data:
                raise LbError(
                    "document changed before send; inspect current instruction",
                    EXIT_REFUSED,
                )
            target, value = unified.locate(current.root, current.path, required=True)
            if unified.section_token(value, "execution") != execution_token:
                raise LbError("execution changed before send", EXIT_REFUSED)
            if value.get("documents") != envelope.get("documents"):
                raise LbError("document evidence changed before send", EXIT_REFUSED)
            if not delivery_started(value["execution"], task_id, request):
                require_ready(current, value, task_id, binding["subject"]["subject_id"])
            value["execution"]["operations"][operation_id] = {
                "id": operation_id,
                "request": request,
                "outcome": "unknown",
                "receipt": None,
                "provenance": "adapter",
            }
            unified.publish(target, value)
            intent_saved = True

    # The session action lock spans transport; the run writer only spans local writes.
    from contextlib import nullcontext

    with nullcontext() if dry_run else observation.action_lock(doc, native):
        result = herdr.control(
            native,
            "send",
            expected_session,
            expected_observation,
            message,
            dry_run,
            before_mutation=persist,
        )
        if dry_run:
            return Result(result | {"record_saved": False})
        if not intent_saved:
            raise LbError(
                "adapter omitted durable intent; reconcile without resend", EXIT_REFUSED
            )
        try:
            with unified.writer(doc.root, doc.path):
                target, value = unified.locate(doc.root, doc.path, required=True)
                op = value["execution"]["operations"][operation_id]
                op.update(outcome="submitted", receipt=result["receipt"])
                unified.publish(target, value)
                token = unified.section_token(value, "execution")
        except (OSError, LbError):
            return Result(
                result
                | {
                    "record_saved": False,
                    "effect": "transport occurred; reconcile without resend",
                },
                EXIT_REFUSED,
            )
    return Result(
        result | {"record_saved": True, "operation": op, "version_token": token}
    )
