"""Preparation transport and observation for explicitly approved checks."""

import hashlib
import json
import uuid
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from logbook_cli import execution, observation, unified
from logbook_cli.adapters import codex_replies, herdr
from logbook_cli.document import (
    EXIT_REFUSED,
    EXIT_USAGE,
    LbError,
    require_preflight_clear,
)
from logbook_cli.lifecycle import get
from logbook_cli.records import single_line
from logbook_cli.repository import require_synced
from logbook_cli.services.agent_observation import _input
from logbook_cli.services.common import Result, load
from logbook_cli.services.preflight_observations import Cache, Observation
from logbook_cli.services.preflight_plan import current_plan
from logbook_cli.services.route_evidence import read_bound_evidence
from logbook_cli.services.route_scope import route_scope
from logbook_cli.services.task_coordination import native_binding

RESULT_LIFETIME = timedelta(minutes=30)


@dataclass(frozen=True)
class Recipient:
    native: dict
    cwd: Path
    digest: str


def check_recipient(run, task_id, check):
    target = run["execution"]["tasks"].get(check.get("binding_task_id", task_id), {})
    binding = target.get("execution_bindings", {}).get(target.get("current_binding_id"))
    environment = check.get("environment")
    if binding is not None:
        if binding["subject"] != {"kind": "agent", "subject_id": check["subject_id"]}:
            raise LbError("current binding differs from the approved subject", EXIT_REFUSED)
        native = native_binding(binding)
        cwd = Path(binding["work_context"]["working_directory"])
        if environment is None:
            return Recipient(native, cwd, unified.digest(binding))
        if native != environment["binding"] or cwd != Path(environment["working_directory"]):
            raise LbError("current binding differs from the approved preparation environment", EXIT_REFUSED)
    if environment is None:
        raise LbError("self-check needs a binding or an approved preparation environment", EXIT_REFUSED)
    return Recipient(
        environment["binding"], Path(environment["working_directory"]), unified.digest(environment)
    )


def _live(recipient):
    if recipient.native["machine"] != "local":
        raise LbError("remote self-check reply channel is unavailable", EXIT_REFUSED)
    pinned, _ = herdr.resolve_binding_scope(recipient.native)
    current = herdr.inspect(pinned)
    actual = current["observation"].get("cwd")
    if (
        not current["live_verified"]
        or not actual
        or Path(actual).resolve() != recipient.cwd.resolve()
    ):
        raise LbError(
            "self-check recipient identity or work directory changed", EXIT_REFUSED
        )
    return pinned, current


def _planned(doc, run, task_id, check_id):
    plan = current_plan(
        run, task_id, read_bound_evidence(doc, run["identity"]), route_scope(doc)
    )
    check = (
        next((row for row in plan["checks"] if row["check_id"] == check_id), None)
        if plan
        else None
    )
    if check is None or not check.get("subject_id") or not check.get("instruction"):
        raise LbError(
            "self-check needs a declared recipient and approved instruction",
            EXIT_REFUSED,
        )
    return plan, check, check_recipient(run, task_id, check)


def _prompt(check, correlation):
    return (
        "Perform only this authorized preparation check. Do not start business work "
        "or change project files. Report the actual checked condition and result.\n"
        f"Check: {check['instruction']}\n"
        "Return a JSON object with keys self_check, status and evidence. "
        f"Use {json.dumps(correlation)} for self_check. "
        'Status must be "passed" or "failed". Evidence must describe the observation.'
    )


def _require_no_pending_reply(operations, request, cwd, now):
    for operation in operations.values():
        recorded = operation["request"]
        if operation["outcome"] != "submitted" or any(
            recorded.get(key) != value for key, value in request.items()
        ):
            continue
        sent_at = datetime.fromisoformat(recorded["intent_at"])
        retry_at = sent_at + RESULT_LIFETIME
        if now >= retry_at:
            continue
        reply = codex_replies.read_reply(
            request["session_id"],
            cwd,
            recorded["correlation"],
            recorded["message_digest"],
            sent_at,
        )
        if reply is None:
            raise LbError(
                "inspect the original submitted self-check before sending another. "
                f"If its reply is unavailable, retry after {retry_at.isoformat()}",
                EXIT_REFUSED,
            )


def send(root, log, input_file, execution_token, dry_run=False):
    data = _input(load(root, log), input_file)
    if not isinstance(data, dict) or set(data) != {
        "task_id",
        "check_id",
        "operation_id",
    }:
        raise LbError(
            "self-check requires task_id, check_id and operation_id", EXIT_USAGE
        )
    task_id = single_line(data["task_id"], "task_id")
    check_id = single_line(data["check_id"], "check_id")
    operation_id = single_line(data["operation_id"], "operation_id")
    doc, task = require_synced(root, log, task_id)
    require_preflight_clear(doc)
    if (
        get(doc)["value"] != "active"
        or task.human
        or task.effective_state not in {"pending", "active"}
    ):
        raise LbError("preparation requires an active agent Task", EXIT_REFUSED)
    _, run = unified.locate(doc.root, doc.path, required=True)
    if unified.section_token(run, "execution") != execution_token:
        raise LbError("execution version conflict", EXIT_REFUSED)
    plan, check, recipient = _planned(doc, run, task_id, check_id)
    operations = run["execution"]["operations"]
    request = {
        "action": "self-check",
        "run_id": run["identity"]["run_id"],
        "task_id": task_id,
        "check_id": check_id,
        "recipient": check["subject_id"],
        "session_id": recipient.native["session_id"],
        "binding_digest": recipient.digest,
        "plan_digest": unified.digest(plan),
    }
    prior = operations.get(operation_id)
    if prior is not None:
        if any(prior["request"].get(key) != value for key, value in request.items()):
            raise LbError("operation ID already binds another self-check", EXIT_REFUSED)
        return Result(
            {"operation": prior, "replayed_record": True, "record_saved": False}
        )
    if any(op["outcome"] == "unknown" for op in operations.values()):
        raise LbError(
            "unknown delivery must be reconciled before another preparation send",
            EXIT_REFUSED,
        )
    execution.require_delegation(doc, owner=check["subject_id"], task_id=task_id)

    with nullcontext() if dry_run else observation.action_lock(doc, recipient.native):
        pinned, current = _live(recipient)
        cwd = recipient.cwd
        correlation = uuid.uuid4().hex
        message = _prompt(check, correlation)
        sent_at = datetime.now(timezone.utc)
        prompt_digest = hashlib.sha256(message.encode()).hexdigest()
        # A missing reply is expected. A missing channel must stop the send.
        codex_replies.read_reply(
            request["session_id"], cwd, correlation, prompt_digest, sent_at
        )
        _require_no_pending_reply(operations, request, cwd, sent_at)
        request.update(
            correlation=correlation,
            message_digest=prompt_digest,
            intent_at=sent_at.isoformat(),
            recipient_environment={
                "binding": recipient.native,
                "working_directory": str(cwd),
            },
        )
        intent = {
            "id": operation_id,
            "request": request,
            "outcome": "unknown",
            "receipt": None,
            "provenance": "adapter",
        }

        def persist():
            with unified.writer(doc.root, doc.path):
                latest, _ = require_synced(root, log, task_id)
                target, current_run = unified.locate(
                    latest.root, latest.path, required=True
                )
                if (
                    latest.data != doc.data
                    or unified.section_token(current_run, "execution")
                    != execution_token
                ):
                    raise LbError(
                        "Task or execution changed before preparation send",
                        EXIT_REFUSED,
                    )
                actual_plan, _, actual_recipient = _planned(
                    latest, current_run, task_id, check_id
                )
                if actual_plan != plan or actual_recipient != recipient:
                    raise LbError(
                        "self-check authorization or recipient changed", EXIT_REFUSED
                    )
                current_run["execution"]["operations"][operation_id] = intent
                unified.publish_run(doc.root, target, current_run)

        result = herdr.control(
            pinned,
            "send",
            request["session_id"],
            current["observation_token"],
            message,
            dry_run,
            before_mutation=persist,
        )
        if dry_run:
            return Result(result | {"record_saved": False})
        with unified.writer(doc.root, doc.path):
            target, latest_run = unified.locate(doc.root, doc.path, required=True)
            operation = latest_run["execution"]["operations"][operation_id]
            if operation != intent:
                raise LbError(
                    "preparation intent changed; reconcile without resending",
                    EXIT_REFUSED,
                )
            operation.update(outcome="submitted", receipt=result["receipt"])
            unified.publish_run(doc.root, target, latest_run)
            token = unified.section_token(latest_run, "execution")
    return Result(
        {"operation": operation, "version_token": token, "record_saved": True}
    )


def collect(root, log, input_file, dry_run=False):
    doc = load(root, log)
    data = _input(doc, input_file)
    if not isinstance(data, dict) or set(data) != {"operation_id"}:
        raise LbError("preflight observation requires only operation_id", EXIT_USAGE)
    op_id = single_line(data["operation_id"], "operation_id")
    _, run = unified.locate(doc.root, doc.path, required=True)
    op = run["execution"]["operations"].get(op_id)
    if (
        not op
        or op["request"].get("action") != "self-check"
        or op["outcome"] == "not_submitted"
    ):
        raise LbError("no matching preparation operation", EXIT_REFUSED)
    request = op["request"]
    task_id, check_id = request["task_id"], request["check_id"]
    plan, check, recipient = _planned(doc, run, task_id, check_id)
    if (
        unified.digest(plan) != request["plan_digest"]
        or recipient.digest != request["binding_digest"]
    ):
        raise LbError("self-check scope or environment changed", EXIT_REFUSED)
    _live(recipient)
    reply = codex_replies.read_reply(
        request["session_id"],
        recipient.cwd,
        request["correlation"],
        request["message_digest"],
        datetime.fromisoformat(request["intent_at"]),
    )
    if reply is None:
        raise LbError(
            "no attributable self-check reply in the current session", EXIT_REFUSED
        )
    if op["outcome"] == "unknown":
        raise LbError(
            "reconcile the original preparation operation before using its reply",
            EXIT_REFUSED,
        )
    row = Observation(
        task_id=task_id,
        check_id=check_id,
        subject_id=check["subject_id"],
        environment_ref=request["binding_digest"],
        scope_ref=plan["scope_ref"],
        candidate_ref=plan["candidate_ref"],
        check_ref=unified.digest({"check": check, "source": plan["source"]}),
        response_ref=op_id,
        source=reply.digest,
        status=reply.status,
        evidence=reply.evidence,
        checked_at=reply.observed_at,
        expires_at=(
            datetime.fromisoformat(reply.observed_at) + RESULT_LIFETIME
        ).isoformat(),
    )
    now = datetime.now(timezone.utc)
    if not row.current(now):
        raise LbError(
            "self-check reply expired; run the affected check again", EXIT_REFUSED
        )
    changed = False
    if not dry_run:
        changed = Cache(doc.root, request["run_id"]).record(row, now=now)
    return Result(
        {
            "task_id": task_id,
            "check_id": check_id,
            "subject_id": row.subject_id,
            "environment_ref": row.environment_ref,
            "status": row.status,
            "evidence": row.evidence,
            "expires_at": row.expires_at,
            "changed": changed,
            "dry_run": dry_run,
        }
    )


def verify(doc, run, task_id, plan, gap):
    cache = Cache(doc.root, run["identity"]["run_id"])
    now = datetime.now(timezone.utc)
    for check in plan["checks"]:
        check_id = check["check_id"]
        owner = check["subject_id"]
        try:
            recipient = check_recipient(run, task_id, check)
            row = cache.get(
                (task_id, check_id, owner, recipient.digest),
                scope_ref=plan["scope_ref"],
                candidate_ref=plan["candidate_ref"],
                check_ref=unified.digest({"check": check, "source": plan["source"]}),
                now=now,
            )
            if row is not None:
                _live(recipient)
        except (LbError, OSError) as exc:
            gap("self_check", str(exc), {"object": check_id, "owner": owner})
            continue
        if row is None:
            gap(
                "self_check",
                "Collect an applicable self-check reply.",
                {"object": check_id, "owner": owner},
            )
        elif row.status != "passed":
            gap(
                "self_check",
                "Resolve the failed self-check and verify it again.",
                {
                    "object": check_id,
                    "owner": owner,
                    "status": row.status,
                    "source": row.source,
                    "evidence": row.evidence,
                },
            )
