"""Journal one send around its external effect; unknown outcomes never auto-retry."""

import copy
import hashlib
import json

from logbook_cli import execution, records
from logbook_cli.adapters import herdr
from logbook_cli.document import EXIT_REFUSED, LbError
from logbook_cli.services.common import Result

DISPATCH_PACKAGE_FIELDS = (
    "task_id", "owner", "scope", "exclusions", "inputs",
    "completion", "escalation",
)
DISPATCH_BINDING_FIELDS = (
    "machine", "workspace_id", "tab_id", "pane_id", "agent_id", "session_id",
)


def legacy_digest(value, fields):
    return hashlib.sha256(
        json.dumps({key: value[key] for key in fields}, sort_keys=True).encode()
    ).hexdigest()


def legacy_binding_digest(binding):
    fields = DISPATCH_BINDING_FIELDS
    if "cli_launcher" in binding:
        fields += ("cli_launcher",)
    return legacy_digest(binding, fields)


def require_matching_versions(
    binding,
    expected_observation,
    *,
    working_directory=None,
    cli_launcher=None,
    ssh_target=None,
):
    from logbook_cli.services.task_coordination import launcher_versions

    sender, recipient = launcher_versions(
        binding,
        expected_observation,
        working_directory=working_directory,
        cli_launcher=cli_launcher,
        ssh_target=ssh_target,
    )
    if not sender.version or not sender.implementation or sender != recipient:

        def describe(identity):
            return f"{identity.version or 'unknown'} (implementation {identity.implementation or 'unknown'})"

        raise LbError(
            f"Delegation blocked: sender CLI {describe(sender)}, "
            f"recipient CLI {describe(recipient)}. Verify the bound launcher and CLI build.",
            EXIT_REFUSED,
        )


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
    request = {
        "dispatch_id": dispatch["id"],
        "recipient": dispatch["owner"],
        "session_id": binding["session_id"],
        "binding_digest": legacy_binding_digest(binding),
        "message_digest": hashlib.sha256(message.encode()).hexdigest(),
        "package_digest": legacy_digest(dispatch, DISPATCH_PACKAGE_FIELDS),
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
    projected = execution.projection(state, dispatch_id=dispatch["id"])
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

    native, ssh_target = herdr.resolve_binding_scope(binding)
    require_matching_versions(
        native,
        expected_observation,
        cli_launcher=binding.get("cli_launcher"),
        ssh_target=ssh_target,
    )
    # The adapter calls persist_intent after live preconditions, before transport.
    result = herdr.control(
        native,
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


def task_send_guard(ex, task_id, operation_id, request, *, released=False):
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
    delivery_started(ex, task_id, request, released=released)
    return None


def delivery_started(ex, task_id, request, *, released=False):
    """Establish first action separately from transport and protect replay."""
    outcomes = {
        fact["operation_id"]: fact["outcome"]
        for fact in ex.get("facts", ())
        if fact["kind"] == "business-action"
    }
    started = False
    for operation_id, op in ex["operations"].items():
        prior = op["request"]
        if (
            execution.operation_task(op) != task_id
            or op["outcome"] != "submitted"
            or prior.get("action") == "self-check"
        ):
            continue
        if op.get("provenance") == "takeover":
            if released:
                continue
            raise LbError("Captain already started this Task", EXIT_REFUSED)
        if op.get("legacy_attempt_ids"):
            raise LbError("Legacy terminal Attempt already started this Task", EXIT_REFUSED)
        outcome = outcomes.get(operation_id)
        if outcome is None:
            raise LbError(
                "Submitted delivery has no business-action outcome; reconcile first",
                EXIT_REFUSED,
            )
        if outcome == "started":
            if "legacy_task_id" in op:
                raise LbError("Legacy delivery already started this Task", EXIT_REFUSED)
            previous_send = prior
            if "release_id" not in request and "release_id" in prior:
                previous_send = {key: value for key, value in prior.items() if key != "release_id"}
            if previous_send == request:
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
    from logbook_cli.services.dependencies import effective
    from logbook_cli.services.readiness import require_ready
    from logbook_cli.services.task_coordination import native_binding
    from logbook_cli.task_identity import lookup, task_dependencies

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
        previous = ex["operations"].get(operation_id)
        if previous is not None:
            if "release_id" in previous["request"]:
                request["release_id"] = previous["request"]["release_id"]
            existing = task_send_guard(ex, task_id, operation_id, request)
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
        for dep in task_dependencies(doc, task, {"id": task_id}):
            if lookup(doc, dep)[0].effective_state != "done":
                raise LbError("hard dependency is not done: " + dep, EXIT_REFUSED)
        from logbook_cli.document import require_preflight_clear
        from logbook_cli.lifecycle import get

        require_preflight_clear(doc)
        if get(doc)["value"] != "active":
            raise LbError("new send requires active Logbook", EXIT_REFUSED)
        release = execution.require_delegation(
            doc, owner=binding["subject"]["subject_id"], task_id=task_id
        )
        released = bool(release and release["scope"] == "task")
        if released:
            from logbook_cli.execution_facts import project

            handoff = project(ex.get("facts", ()), ex, task_id=task_id)
            if not handoff["handoff_reported_complete"]:
                if handoff["reported_owner"] == "unknown":
                    raise LbError(
                        "ownership is unknown or conflicting; observe a safe boundary before handoff",
                        EXIT_REFUSED,
                    )
                if any(
                    op["outcome"] != "not_submitted"
                    and op["request"].get("release_id") == release["id"]
                    and op["request"].get("binding_id") == binding_id
                    for op in ex["operations"].values()
                ):
                    raise LbError("Task handoff is already pending on this binding", EXIT_REFUSED)
                request["release_id"] = release["id"]
        task_send_guard(ex, task_id, operation_id, request, released=released)
        first_start = not delivery_started(ex, task_id, request, released=released)
        if first_start:
            require_ready(doc, envelope, task_id, binding["subject"]["subject_id"])
    intent_saved = False
    intent = {
        "id": operation_id,
        "request": request,
        "outcome": "unknown",
        "receipt": None,
        "provenance": "adapter",
    }

    def persist():
        nonlocal intent_saved
        with unified.writer(doc.root, doc.path):
            current, _ = require_synced(root, log, task_id)
            if current.data != doc.data:
                raise LbError(
                    "document changed before send; inspect current instruction",
                    EXIT_REFUSED,
                )
            if effective(current) != effective(doc):
                raise LbError(
                    "Task dependencies changed before send; reread route",
                    EXIT_REFUSED,
                )
            target, value = unified.locate(current.root, current.path, required=True)
            if unified.section_token(value, "execution") != execution_token:
                raise LbError("execution changed before send", EXIT_REFUSED)
            if value.get("documents") != envelope.get("documents"):
                raise LbError("document evidence changed before send", EXIT_REFUSED)
            if not delivery_started(
                value["execution"], task_id, request, released=released
            ):
                require_ready(current, value, task_id, binding["subject"]["subject_id"])
            value["execution"]["operations"][operation_id] = intent
            unified.publish_run(doc.root, target, value)
            intent_saved = True

    # The session action lock spans transport; the run writer only spans local writes.
    from contextlib import nullcontext

    with nullcontext() if dry_run else observation.action_lock(doc, native):
        pinned, ssh_target = herdr.resolve_binding_scope(native)
        if first_start:
            work_context = binding.get("work_context", {})
            require_matching_versions(
                pinned,
                expected_observation,
                working_directory=work_context.get("working_directory"),
                cli_launcher=work_context.get("cli_launcher"),
                ssh_target=ssh_target,
            )
        result = herdr.control(
            pinned,
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
                operations = value["execution"]["operations"]
                if operations.get(operation_id) != intent:
                    raise LbError("send intent changed before recording receipt", EXIT_REFUSED)
                op = {**intent, "outcome": "submitted", "receipt": result["receipt"]}
                operations[operation_id] = op
                unified.publish_run(doc.root, target, value)
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
