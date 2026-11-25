"""Authorized declarations of the self-checks a Task requires."""

from pathlib import PurePosixPath

from logbook_cli import unified
from logbook_cli.adapters.herdr import validate_session_binding
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
from logbook_cli.services.common import Result
from logbook_cli.services.route_evidence import (
    active_records,
    current_records,
    read_bound_evidence,
)
from logbook_cli.services.route_scope import route_scope


def declaration(payload):
    fields = {"actor", "scope_ref", "candidate_ref", "checks"}
    if not isinstance(payload, dict) or set(payload) != fields:
        raise LbError(
            "preflight plan requires actor, scope_ref, candidate_ref and checks",
            EXIT_USAGE,
        )
    for key in fields - {"checks"}:
        single_line(payload[key], key)
    checks = payload["checks"]
    if not isinstance(checks, list):
        raise LbError("preflight checks must be a list", EXIT_USAGE)
    seen = set()
    for row in checks:
        if not isinstance(row, dict) or set(row) - {
            "instruction",
            "binding_task_id",
            "environment",
        } != {"check_id", "subject_id"}:
            raise LbError(
                "each preflight check requires check_id and subject_id", EXIT_USAGE
            )
        check = single_line(row["check_id"], "check_id")
        if row["subject_id"] is not None:
            single_line(row["subject_id"], "subject_id")
        for field in ("instruction", "binding_task_id"):
            if field in row:
                single_line(row[field], field)
        if "environment" in row:
            environment = row["environment"]
            if (
                row["subject_id"] is None
                or not isinstance(environment, dict)
                or set(environment) != {"binding", "working_directory"}
            ):
                raise LbError("preparation environment requires an approved subject and native identity", EXIT_USAGE)
            validate_session_binding(environment["binding"])
            cwd = single_line(environment["working_directory"], "working_directory")
            if "\x00" in cwd or not PurePosixPath(cwd).is_absolute():
                raise LbError("preparation working directory must be absolute", EXIT_USAGE)
        if check in seen:
            raise LbError("duplicate preflight check", EXIT_USAGE)
        seen.add(check)
    return {**payload, "checks": sorted(checks, key=lambda row: row["check_id"])}


def grant_source(evidence, scope, task_id, plan):
    """Match the complete check set, including an explicitly authorized empty set."""
    scope_ref = scope["task_scopes"].get(task_id)
    if evidence is None or scope_ref is None or scope_ref != plan["scope_ref"]:
        raise LbError(
            "preflight plan requires its current confirmed Task scope", EXIT_REFUSED
        )
    route_ref = scope["route_ref"]
    confirmations = current_records(
        active_records("confirmations", evidence["confirmations"]),
        task_id,
        route_ref,
        scope_ref,
    )
    if not confirmations or any(
        row.get("status") != "confirmed" for row in confirmations
    ):
        raise LbError(
            "confirm the current Task scope before declaring checks", EXIT_REFUSED
        )
    grant_rows = [
        row
        for row in active_records("grants", evidence["grants"])
        if row.get("task_id") == task_id
        and row.get("actor") == plan["actor"]
        and row.get("action") == "preflight-plan"
    ]
    approved = [
        row
        for row in current_records(grant_rows, task_id, route_ref, scope_ref)
        if row.get("status") == "granted"
    ]
    sources = {row["source"] for row in approved}
    if (
        len(sources) != 1
        or any(
            row.get("candidate_ref") != plan["candidate_ref"]
            or row.get("checks") != plan["checks"]
            for row in approved
        )
        or any(row.get("status") == "revoked" for row in grant_rows)
    ):
        raise LbError(
            "record authorization for this exact preflight check set", EXIT_REFUSED
        )
    return sources.pop()


def current_plan(run, task_id, evidence, scope):
    managed = run.get("preflight", {})
    if task_id not in managed.get("enrolled", ()):
        return None
    stored = managed.get("plans", {}).get(task_id)
    if not isinstance(stored, dict) or "source" not in stored:
        raise LbError(
            "record the required preflight checks for this Task", EXIT_REFUSED
        )
    plan = declaration({key: value for key, value in stored.items() if key != "source"})
    if stored["source"] != grant_source(evidence, scope, task_id, plan):
        raise LbError(
            "preflight plan authorization changed; record it again", EXIT_REFUSED
        )
    return {**plan, "source": stored["source"]}


def save(root, log, task_id, input_file, token, dry_run=False):
    doc, _ = require_synced(root, log, task_id)
    plan = declaration(_input(doc, input_file))
    with unified.writer(doc.root, doc.path, dry_run):
        doc, task = require_synced(root, log, task_id)
        target, run = unified.locate(doc.root, doc.path, required=True)
        if unified.section_token(run, "execution") != token:
            raise LbError("execution version conflict; reread context", EXIT_REFUSED)
        require_preflight_clear(doc)
        if task.human or task.effective_state not in {"pending", "active"}:
            raise LbError("select a pending or active agent Task", EXIT_REFUSED)
        if get(doc)["value"] in {"paused", "completed", "terminated"}:
            raise LbError("lifecycle stops ordinary writes", EXIT_REFUSED)
        source = grant_source(
            read_bound_evidence(doc, run["identity"]), route_scope(doc), task_id, plan
        )
        managed = run.setdefault("preflight", {"enrolled": [], "plans": {}})
        record = {**plan, "source": source}
        changed = (
            task_id not in managed["enrolled"]
            or managed["plans"].get(task_id) != record
        )
        if changed:
            if task_id not in managed["enrolled"]:
                managed["enrolled"].append(task_id)
            managed["plans"][task_id] = record
            if not dry_run:
                unified.publish_run(doc.root, target, run)
        return Result(
            {
                "changed": changed,
                "dry_run": dry_run,
                "task_id": task_id,
                "plan": record,
                "execution_version_token": token
                if dry_run
                else unified.section_token(run, "execution"),
            }
        )
