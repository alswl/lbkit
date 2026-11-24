"""Read first-start evidence and evaluate admission without mutating the run."""

from datetime import datetime, timezone

from logbook_cli import execution as execution_records
from logbook_cli import task_identity
from logbook_cli.document import EXIT_REFUSED, LbError, require_preflight_clear
from logbook_cli.services.preflight_findings import missing_skills, summarize
from logbook_cli.services.route_evidence import (
    active_records,
    bound_thinking,
    parse_evidence,
)
from logbook_cli.services.route_scope import route_scope


def unresolved_operation(execution, task_id, *, across_tasks=False):
    observed = {
        fact["operation_id"]: fact["outcome"]
        for fact in execution.get("facts", ())
        if fact["kind"] == "business-action"
    }
    return any(
        op["outcome"] == "unknown"
        and (across_tasks or execution_records.operation_task(op) == task_id)
        or (
            op["outcome"] == "submitted"
            and execution_records.operation_task(op) == task_id
            and op.get("provenance") != "takeover"
            and (
                op.get("legacy_attempt_ids")
                or operation_id not in observed
                or "legacy_task_id" in op and observed[operation_id] == "started"
            )
        )
        for operation_id, op in execution["operations"].items()
    )


def evaluate(doc, run, task_id, actor=None, action="dispatch"):
    identity = run["identity"]
    gaps = []
    checks = {}

    def gap(kind, message, observation=None):
        checks["preflight" if kind == "skill" else kind] = "blocked"
        observation = observation or {}
        gaps.append(
            {
                "object": observation.get("object", kind),
                "step": task_id,
                "status": observation.get("status", "unverified"),
                "evidence": observation.get("source"),
                "owner": observation.get("owner"),
                "clear_when": message,
                "human_action": observation.get("human_action"),
            }
        )

    route_ref = None
    decision = "blocked"
    execution = run["execution"]
    if unresolved_operation(execution, task_id, across_tasks=True):
        decision = "reconcile"
        gap("operation", "Reconcile the existing operation before starting.")
    else:
        try:
            require_preflight_clear(doc)
            scope = route_scope(doc)
            route_ref = scope["route_ref"]
            evidence = []
            for name in identity.get("document_paths", ()):
                if name != identity.get("log_path"):
                    path = bound_thinking(doc, identity, name)
                    value = parse_evidence(path.read_bytes().decode())
                    if value is not None:
                        evidence.append(value)
            if len(evidence) != 1 or evidence[0]["run_ref"] != identity["run_id"]:
                gap(
                    "evidence",
                    "Record current route confirmation and preflight in bound Thinking.",
                )
            else:
                task, _, _ = task_identity.lookup(doc, task_id)
                if task.human or task.effective_state not in {"pending", "active"}:
                    gap("task", "Select a pending or active agent task.")
                for dependency in task_identity.dependencies(task):
                    if (
                        task_identity.lookup(doc, dependency)[0].effective_state
                        != "done"
                    ):
                        gap("dependency", f"Complete task {dependency}.")
                for name in ("confirmation", "preflight", "authorization"):
                    checks[name] = "satisfied"
                runtime = execution.get("tasks", {}).get(task_id, {})
                binding = runtime.get("execution_bindings", {}).get(
                    runtime.get("current_binding_id"), {}
                )
                _evaluate_evidence(
                    evidence[0],
                    route_ref,
                    task_id,
                    actor,
                    action,
                    gap,
                    task=task,
                    doc=doc,
                    scope_ref=scope["task_scopes"].get(task_id),
                    machine=binding.get("machine") if action == "dispatch" else "local",
                )
        except (LbError, OSError, UnicodeError) as exc:
            gap("route", str(exc))
        if not gaps:
            decision = "ready"
    return {
        "task_id": task_id,
        "route_ref": route_ref,
        "decision": decision,
        "checks": checks,
        "gaps": gaps,
        "human_actions": [
            entry["human_action"] for entry in gaps if entry["human_action"]
        ],
        "recovery": [entry["clear_when"] for entry in gaps],
    }


def _evaluate_evidence(
    value,
    route_ref,
    task_id,
    actor,
    action,
    gap,
    *,
    task=None,
    doc=None,
    scope_ref=None,
    machine=None,
):
    def current(records):
        return [
            row
            for row in records
            if (
                (
                    row.get("scope") == task_id
                    and scope_ref is not None
                    and row.get("route_ref") == scope_ref
                )
                or (
                    row.get("scope") in (None, "route")
                    and row.get("route_ref") == route_ref
                )
            )
            and isinstance(row.get("source"), str)
            and row["source"].strip()
        ]

    confirmations = current(active_records("confirmations", value["confirmations"]))
    if not confirmations or any(
        row.get("status") != "confirmed" for row in confirmations
    ):
        gap(
            "confirmation",
            "Confirm the current route with the route owner and resolve conflicting decisions.",
        )

    observations = [
        row
        for row in current(active_records("observations", value["observations"]))
        if (row.get("task_id") == task_id or row.get("scope") == "route")
        and row.get("action") in (None, action)
    ]
    unresolved = summarize(observations)
    if not unresolved and not any(
        row.get("task_id") == task_id and row.get("status") == "ready"
        for row in observations
    ):
        gap("preflight", "Record a current ready preflight for the task.")
    for observation in unresolved:
        gap(
            "preflight",
            observation.get("clear_when") or "Resolve the recorded preflight finding.",
            observation,
        )
    for observation in observations:
        if observation.get("status") != "ready":
            continue
        if not observation_current(observation, machine):
            gap("preflight", "Recheck expired or mismatched environment evidence.")
            continue
        if task is not None and observation.get("task_id") == task_id:
            applicable = observation.get("skills")
            if (
                observation.get("criteria_digest") != task_identity.criteria(task)
                or not isinstance(applicable, list)
                or not all(
                    isinstance(name, str) and name.strip() for name in applicable
                )
                or not inputs_current(doc, observation.get("inputs", {}))
            ):
                gap("preflight", "Recheck current task criteria, skills and inputs.")
            else:
                for name in missing_skills(task, applicable):
                    gap(
                        "skill",
                        f"Record the verified applicable skill {name} on the task.",
                    )
        elif doc is not None and not inputs_current(doc, observation.get("inputs", {})):
            gap("preflight", "Recheck current route dependencies.")

    grants = [
        row
        for row in active_records("grants", value["grants"])
        if row.get("task_id") == task_id
        and row.get("actor") == actor
        and row.get("action") == action
    ]
    if any(row.get("status") == "revoked" for row in grants) or not any(
        row.get("status") == "granted" for row in current(grants)
    ):
        gap("authorization", "Record applicable execution authorization.")


def inputs_current(doc, inputs):
    """Check declared workspace files, including candidate manifests and skill definitions."""
    import hashlib

    from logbook_cli.document import safe_path

    if not isinstance(inputs, dict):
        return False
    for name, expected in inputs.items():
        if not isinstance(name, str) or not isinstance(expected, str) or doc is None:
            return False
        path = safe_path(doc.root, name)
        if (
            not path.is_file()
            or hashlib.sha256(path.read_bytes()).hexdigest() != expected
        ):
            return False
    return True


def observation_current(observation, machine):
    if "machine" in observation and observation["machine"] != machine:
        return False
    if "expires_at" not in observation:
        return True
    try:
        expires = datetime.fromisoformat(observation["expires_at"])
        return expires.tzinfo is not None and expires > datetime.now(timezone.utc)
    except (TypeError, ValueError):
        return False


def require_ready(doc, run, task_id, actor):
    result = evaluate(doc, run, task_id, actor)
    if result["decision"] != "ready":
        raise LbError("first start: " + " ".join(result["recovery"]), EXIT_REFUSED)


def takeover_transition(
    operations, operation_id, request, transition, evidence=None, nonstarts=()
):
    existing = operations.get(operation_id)
    if existing and existing["request"] != request:
        raise LbError("operation ID belongs to another request", EXIT_REFUSED)
    if transition == "reserve":
        if existing:
            return existing, False
        for prior_id, operation in operations.items():
            if operation["outcome"] == "unknown" or (
                operation["request"].get("task_id") == request["task_id"]
                and operation["outcome"] == "submitted"
                and prior_id not in nonstarts
            ):
                raise LbError(
                    "reconcile the existing operation before takeover", EXIT_REFUSED
                )
        return {
            "id": operation_id,
            "request": request,
            "outcome": "unknown",
            "receipt": None,
            "provenance": "takeover",
        }, True
    if transition not in {"started", "not_started"} or not existing:
        raise LbError(
            "transition requires an existing takeover operation", EXIT_REFUSED
        )
    if not isinstance(evidence, str) or not evidence.strip():
        raise LbError("record observed business-action evidence", EXIT_REFUSED)
    outcome = "submitted" if transition == "started" else "not_submitted"
    resolved = {
        **existing,
        "outcome": outcome,
        "receipt": {"business_action": transition, "source": evidence},
    }
    if existing["outcome"] != "unknown" and existing != resolved:
        raise LbError("takeover operation is already resolved", EXIT_REFUSED)
    return resolved, False


def record_takeover(
    root, log, task_id, actor, operation_id, token, transition, evidence
):
    from logbook_cli import execution_facts, unified
    from logbook_cli.lifecycle import get
    from logbook_cli.repository import require_synced
    from logbook_cli.services.common import Result

    execution_facts.text(operation_id)
    execution_facts.text(actor)
    doc, _ = require_synced(root, log, task_id)
    with unified.writer(doc.root, doc.path):
        doc, _ = require_synced(root, log, task_id)
        target, run = unified.locate(doc.root, doc.path, required=True)
        if token != unified.section_token(run, "execution"):
            raise LbError("execution version conflict", EXIT_REFUSED)
        ex = run["execution"]
        request = {
            "run_id": run["identity"]["run_id"],
            "task_id": task_id,
            "actor": actor,
            "action": "takeover",
        }
        op, may_start = takeover_transition(
            ex["operations"],
            operation_id,
            request,
            transition,
            evidence,
            {
                fact["operation_id"]
                for fact in ex["facts"]
                if fact["kind"] == "business-action"
                and fact["outcome"] == "not_started"
            },
        )
        if may_start:
            owner = execution_facts.project(ex["facts"])["reported_owner"]
            if owner != actor or get(doc)["value"] != "active":
                raise LbError(
                    "takeover requires active Logbook and observed sole ownership",
                    EXIT_REFUSED,
                )
            result = evaluate(doc, run, task_id, actor, "takeover")
            if result["decision"] != "ready":
                raise LbError(
                    "first start: " + " ".join(result["recovery"]), EXIT_REFUSED
                )
        if ex["operations"].get(operation_id) != op:
            ex["operations"][operation_id] = op
            unified.publish(target, run)
        return Result(
            {
                "operation": op,
                "may_start": may_start,
                "execution_version_token": unified.section_token(run, "execution"),
            }
        )
