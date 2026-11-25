"""Read-only close-out inventory and guarded Thinking event append."""

from __future__ import annotations

import difflib

from logbook_cli import records, state, unified
from logbook_cli.document import (
    EXIT_REFUSED,
    EXIT_USAGE,
    LbError,
    links_for,
    require_preflight_clear,
    require_version_token,
    resolve_link_target,
    safe_path,
)
from logbook_cli.link_records import observations, occurrence, timestamp
from logbook_cli.models import Field
from logbook_cli.repository import event_context
from logbook_cli.run_metrics import calculate, event_rows
from logbook_cli.services.common import Result, load, save
from logbook_cli.views import state_snapshot


def audit_links(doc):
    links = links_for(doc)
    obs, errors = observations(doc, links)
    rows = []
    for link in links:
        where = occurrence(doc, link)
        required = any(
            a.line == link["line"] and a.kind is Field.ARTIFACT
            for stage in doc.stages
            for task in stage.tasks
            for a in task.annotations
        )
        candidates = [
            r
            for r in obs
            if r["applicable"]
            and r["line"] == link["line"]
            and r["target"] == link["target"]
            and r["label"] == link["label"]
        ]
        outcome, basis = "unknown", None
        if candidates:
            latest = max(timestamp(r["observed_at"]) for r in candidates)
            current = [r for r in candidates if timestamp(r["observed_at"]) == latest]
            if len({(r["outcome"], r["result_identity"]) for r in current}) == 1:
                outcome = current[0]["outcome"]
                basis = current[0]["basis"]
        target_status, _ = resolve_link_target(doc.root, doc.path, link["target"])
        existence = {
            "ok": "exists",
            "missing": "missing",
            "outside": "outside-root",
            "unreadable": "unreadable",
            "external": "unobserved",
        }[target_status]
        if existence == "missing":
            outcome = "unavailable"
        rows.append(
            {
                **link,
                "task": where["task"],
                "required": required,
                "outcome": outcome,
                "existence": existence,
                "basis": basis,
            }
        )
    return {
        "links": rows,
        "link_verifications": obs,
        "errors": errors,
        "coverage": "artifact annotations only; other links are references",
        "delivery_ready": not errors
        and all(r["outcome"] == "verified" for r in rows if r["required"]),
    }


def thinking_path(doc, value):
    # The caller supplies the adapter-resolved companion, never a guessed name.
    path = safe_path(doc.root, value)
    if path == doc.path:
        raise LbError("Thinking cannot be the Logbook", EXIT_REFUSED)
    return path


def bound_companion(doc, path, run):
    identity = run["identity"]
    if (
        state.section(doc.path, doc.root) != identity["log_path"]
        or state.project(path, doc.root) != state.project(doc.path, doc.root)
    ):
        raise LbError(
            "expected the Logbook and a companion in its project", EXIT_REFUSED
        )
    key = state.section(path, doc.root)
    if key not in identity["document_paths"] or key == identity["log_path"]:
        raise LbError("Thinking must be a companion bound to this run", EXIT_REFUSED)
    return key


def state_events(doc):
    if not doc.markdown_authority:
        return event_rows(row for _, row in records.read(doc, "run-event"))
    return event_rows(
        [
            *doc.legacy_history.get("run-event", {}).values(),
            *doc.legacy_metadata.get("run-event", {}).values(),
            *doc.run_events,
        ]
    )


def metrics(root, log, thinking, run_id, scope):
    doc = load(root, log)
    if not thinking:
        return {
            "coverage": "unknown",
            "reason": "adapter-resolved --thinking not supplied",
        }
    path = thinking_path(doc, thinking)
    if doc.markdown_authority:
        _, run = unified.locate(doc.root, doc.path, required=True)
        bound_companion(doc, path, run)
    record = load(root, str(path))
    if record.markdown_authority != doc.markdown_authority:
        raise LbError(
            "Thinking must use the same run authority as the Logbook", EXIT_REFUSED
        )
    try:
        items = state_events(record)
        ids = sorted({e["run_id"] for e in items})
        if run_id is None:
            if len(ids) != 1:
                return {
                    "coverage": "unknown",
                    "reason": "select --run-id",
                    "run_ids": ids,
                }
            run_id = ids[0]
        return calculate(items, run_id, scope)
    except (ValueError, TypeError, KeyError) as exc:
        raise LbError(f"invalid run events: {exc}", EXIT_USAGE) from exc


def check_event(record, item, token):
    require_version_token(record, token)
    records.anchors(record, require_closed=True)
    try:
        event_rows([item])
        old = state_events(record)
        all_events = event_rows([*old, item])
        scopes = {}
        for event in all_events:
            scopes.setdefault(event["run_id"], {"logbook"}).add(event["scope"])
        for run_id, names in scopes.items():
            for name in names:
                calculate(all_events, run_id, name)
    except (ValueError, TypeError, KeyError) as exc:
        raise LbError(f"invalid run event: {exc}", EXIT_USAGE) from exc
    return len(old) == len(all_events)


def record_unified_event(doc, path, item, token, dry_run):
    with unified.writer(doc.root, doc.path, dry_run):
        doc = load(str(doc.root), str(doc.path))
        require_preflight_clear(doc)
        target, run = unified.locate(doc.root, doc.path, required=True)
        key = bound_companion(doc, path, run)
        record = load(str(doc.root), str(path))
        replay = check_event(record, item, token)
        prior = run.get("run_events", {}).get(key, [])
        current = prior if replay else [*prior, item]
        result = {
            "path": path.relative_to(doc.root).as_posix(),
            "dry_run": dry_run,
            "changed": not replay,
            "event_id": item["event_id"],
            "replay": replay,
            "version_token": record.token,
        }
        diff = None
        if dry_run:
            label = f"{target.relative_to(doc.root)}#run_events/{key}"
            diff = "".join(
                difflib.unified_diff(
                    unified.encode(prior).decode().splitlines(keepends=True),
                    unified.encode(current).decode().splitlines(keepends=True),
                    fromfile=label,
                    tofile=label,
                )
            )
            result["diff"] = diff
        elif not replay:
            if (
                state.read_regular(doc.root, doc.path) != doc.data
                or state.read_regular(doc.root, path) != record.data
            ):
                raise LbError(
                    "document changed during event recording; reread", EXIT_REFUSED
                )
            run.setdefault("run_events", {})[key] = current
            unified.publish(target, run)
            result["version_token"] = state.token(record.data, event_context(run, key))
        return Result(result, text=diff)


def record_event(root, log, thinking, event_file, token, dry_run):
    doc = load(root, log)
    require_preflight_clear(doc)
    path = thinking_path(doc, thinking)
    try:
        item = state.decode_json(safe_path(doc.root, event_file).read_bytes())
    except (ValueError, TypeError) as exc:
        raise LbError(f"invalid run event: {exc}", EXIT_USAGE) from exc
    if doc.markdown_authority:
        return record_unified_event(doc, path, item, token, dry_run)
    record = load(root, str(path))
    if record.markdown_authority:
        raise LbError(
            "Thinking must use the same run authority as the Logbook", EXIT_REFUSED
        )
    replay = check_event(record, item, token)
    if not replay:
        records.put(record, "run-event", item)
    return save(record, record.text, dry_run, event_id=item["event_id"], replay=replay)


def closeout(root, log, thinking, run_id, scope):
    doc = load(root, log)
    state = state_snapshot(doc)
    tasks = [
        t
        for s in doc.stages
        if s.is_delivery and (scope == "logbook" or s.title == scope)
        for t in s.tasks
    ]
    if scope != "logbook" and not any(
        s.title == scope for s in doc.stages if s.is_delivery
    ):
        raise LbError("unknown Stage scope; use its exact title", EXIT_USAGE)
    inventory = audit_links(doc)
    if scope != "logbook":
        inventory["links"] = [
            r for r in inventory["links"] if r["task"] and r["task"]["stage"] == scope
        ]
        inventory["delivery_ready"] = not inventory["errors"] and all(
            r["outcome"] == "verified" for r in inventory["links"] if r["required"]
        )
    return Result(
        {
            "state": state,
            "scope": scope,
            "checklist": {
                "total": len(tasks),
                "accepted": sum(t.state == "x" for t in tasks),
                "dispositioned": sum(t.state == "-" and t.settled for t in tasks),
                "open": [
                    {"line": t.line, "text": t.text, "human": t.human}
                    for t in tasks
                    if not t.settled
                ],
            },
            "delivery": inventory,
            "metrics": metrics(root, log, thinking, run_id, scope),
            "runtime_cleanup": "requires current executor return; no runtime operations performed",
            "decision": "report only; Captain aligns actual criteria and authorization",
        }
    )
