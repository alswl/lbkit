"""Read first-start evidence and evaluate admission without mutating the run."""

import hashlib
from datetime import datetime, timezone

from logbook_cli import execution as execution_records
from logbook_cli import execution_facts, state, task_identity
from logbook_cli.document import (
    EXIT_REFUSED,
    LbError,
    path_error,
    require_preflight_clear,
)
from logbook_cli.services.preflight_findings import missing_skills, summarize
from logbook_cli.services.preflight_plan import current_plan
from logbook_cli.services.route_evidence import (
    active_records,
    current_records,
    read_bound_evidence,
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
            and op["request"].get("action") != "self-check"
            and (
                op.get("legacy_attempt_ids")
                or operation_id not in observed
                or "legacy_task_id" in op
                and observed[operation_id] == "started"
            )
        )
        for operation_id, op in execution["operations"].items()
    )


def takeover_gap(execution, task_id, actor):
    projected = execution_facts.project(
        execution.get("facts", ()), execution, task_id=task_id
    )
    takeover = projected["takeover"]
    if takeover is None or takeover["origin"] != "explicit":
        return "Record the explicit human takeover instruction before Captain starts."
    if projected["release"] is not None:
        return "Reconcile the authorized handoff before any further Captain start in its scope."
    if (
        actor != execution.get("captain", "captain")
        or projected["reported_owner"] != actor
    ):
        return "Verify the recorded Captain's sole execution ownership before starting."
    return None


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
                "evidence": observation.get("evidence") or observation.get("source"),
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
        if action == "takeover":
            reason = takeover_gap(execution, task_id, actor)
            if reason:
                gap("takeover", reason)
        try:
            require_preflight_clear(doc)
            scope = route_scope(doc)
            route_ref = scope["route_ref"]
            evidence = read_bound_evidence(doc, identity)
            if evidence is None:
                gap(
                    "evidence",
                    "Record current route confirmation and preflight in bound Thinking.",
                )
            else:
                task, _, task_record = task_identity.lookup(doc, task_id)
                if task.human or task.effective_state not in {"pending", "active"}:
                    gap("task", "Select a pending or active agent task.")
                for dependency in task_identity.task_dependencies(doc, task, task_record):
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
                    evidence,
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
                try:
                    plan = current_plan(run, task_id, evidence, scope)
                except LbError as exc:
                    gap("self_check", str(exc))
                else:
                    if plan is not None and plan["checks"]:
                        from logbook_cli.services.self_check import verify

                        verify(doc, run, task_id, plan, gap)
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
        return current_records(records, task_id, route_ref, scope_ref)

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
        task_observation = task is not None and observation.get("task_id") == task_id
        applicable = observation.get("skills")
        if task_observation:
            if (
                observation.get("criteria_digest") != task_identity.criteria(task)
                or not isinstance(applicable, list)
                or not all(
                    isinstance(name, str) and name.strip() for name in applicable
                )
            ):
                gap("preflight", "Recheck current task criteria and skills.")
                continue
        try:
            if (task_observation or doc is not None) and not inputs_current(
                doc, observation.get("inputs", {})
            ):
                gap("preflight", "Recheck current input evidence.")
                continue
        except LbError as exc:
            gap("preflight", str(exc))
            continue
        if task_observation:
            for name in missing_skills(task, applicable):
                gap("skill", f"Record the verified applicable skill {name} on the task.")

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
    """Check declared input digests against files in the Logbook project."""
    if not isinstance(inputs, dict):
        return False
    if not inputs:
        return True
    if doc is None:
        return False
    base = state.project(doc.path, doc.root)
    field = "observations.inputs"
    for name, expected in inputs.items():
        if not isinstance(expected, str):
            raise path_error(field, name, base, "expected a SHA-256 digest string")
        path = state.project_file(base, name, field)
        try:
            with state.open_regular(base, path) as source:
                actual = hashlib.file_digest(source, "sha256").hexdigest()
        except OSError as exc:
            raise path_error(field, name, base, f"cannot read input file: {exc}") from exc
        if actual != expected:
            raise path_error(field, name, base, "SHA-256 digest does not match")
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
                and operation["request"].get("action") != "self-check"
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
    from logbook_cli import unified
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
            if get(doc)["value"] != "active":
                raise LbError("takeover requires active Logbook", EXIT_REFUSED)
            result = evaluate(doc, run, task_id, actor, "takeover")
            if result["decision"] != "ready":
                raise LbError(
                    "first start: " + " ".join(result["recovery"]), EXIT_REFUSED
                )
        if ex["operations"].get(operation_id) != op:
            ex["operations"][operation_id] = op
            unified.publish_run(doc.root, target, run)
        return Result(
            {
                "operation": op,
                "may_start": may_start,
                "execution_version_token": unified.section_token(run, "execution"),
            }
        )
