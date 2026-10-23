"""Read-only close-out inventory and guarded Thinking event append."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import unquote, urlparse

from logbook_cli import records
from logbook_cli.document import (
    EXIT_REFUSED,
    EXIT_USAGE,
    LbError,
    links_for,
    require_preflight_clear,
    require_token,
    safe_path,
)
from logbook_cli.link_records import observations, occurrence, timestamp
from logbook_cli.models import Field
from logbook_cli.run_metrics import calculate, events
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
        target = urlparse(link["target"])
        existence = "unobserved"
        if target.scheme in {"", "file"} and not target.netloc:
            raw = Path(unquote(target.path)).expanduser()
            path = (raw if raw.is_absolute() else doc.path.parent / raw).resolve()
            if path.is_relative_to(doc.root):
                existence = "exists" if path.exists() else "missing"
                if existence == "missing":
                    outcome = "unavailable"
            else:
                existence = "outside-root"
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
        "errors": errors,
        "coverage": "artifact annotations only; other links are references",
        "delivery_ready": not errors
        and all(r["outcome"] == "verified" for r in rows if r["required"]),
    }


def thinking_path(doc, value):
    # Caller supplies the adapter-resolved binding; never guess from filenames.
    path = safe_path(doc.root, value)
    if path == doc.path:
        raise LbError("Thinking cannot be the Logbook", EXIT_REFUSED)
    return str(path.relative_to(doc.root))


def state_events(doc):
    rows = [row for _, row in records.read(doc, "run-event")]
    return (
        events(
            "\n```lb-run-events\n"
            + "\n".join(json.dumps(row) for row in rows)
            + "\n```\n"
        )
        if rows
        else []
    )


def metrics(root, log, thinking, run_id, scope):
    doc = load(root, log)
    if not thinking:
        return {
            "coverage": "unknown",
            "reason": "adapter-resolved --thinking not supplied",
        }
    record = load(root, thinking_path(doc, thinking))
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


def record_event(root, log, thinking, event_file, token, dry_run):
    doc = load(root, log)
    require_preflight_clear(doc)
    record = load(root, thinking_path(doc, thinking))
    require_token(record, token)
    records.read(record, "runtime", require_closed=True)
    try:
        item = json.loads(safe_path(doc.root, event_file).read_text())
        if not isinstance(item, dict):
            raise ValueError("event must be an object")
        body = "\n```lb-run-events\n" + json.dumps(item, ensure_ascii=False) + "\n```\n"
        # Parse the input alone to reject wrong shapes even for an idempotent retry.
        events(body)
        old = state_events(record)
        matches = [
            e
            for e in old
            if (e["run_id"], e["event_id"]) == (item["run_id"], item["event_id"])
        ]
        if matches and matches[0] != item:
            raise ValueError("conflicting event identity")
        if not matches:
            records.put(record, "run-event", item)
        changed = record.text
        all_events = state_events(record)
        for run in {e["run_id"] for e in all_events}:
            for scope in {"logbook"} | {
                e["scope"] for e in all_events if e["run_id"] == run
            }:
                calculate(all_events, run, scope)
    except (ValueError, TypeError, KeyError) as exc:
        raise LbError(f"invalid run event: {exc}", EXIT_USAGE) from exc
    return save(
        record, changed, dry_run, event_id=item["event_id"], replay=bool(matches)
    )


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
