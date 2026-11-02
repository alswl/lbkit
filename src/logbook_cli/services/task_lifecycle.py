"""Single-logbook semantic task transitions; execution receipt is not acceptance."""

import json
import re
import uuid
from datetime import datetime, timezone

from logbook_cli import records
from logbook_cli import task_identity as identity
from logbook_cli.document import (
    EXIT_REFUSED,
    EXIT_USAGE,
    LbError,
    find_task,
    parse_text,
    safe_path,
)
from logbook_cli.services.common import Result, load, save, writable


def identify(root, log, stage, task, task_id, token, dry_run):
    doc = writable(root, log, token)
    records.read(doc, "task", require_closed=True)
    target = find_task(doc, stage, task)
    known = identity.bindings(doc)
    existing = [r for t, _, r in known.values() if t.line == target.line]
    if existing:
        if task_id and existing[0]["id"] != task_id:
            raise LbError("task already has another ID", EXIT_REFUSED)
        return save(doc, doc.text, dry_run, task_id=existing[0]["id"])
    task_id = task_id or "task-" + uuid.uuid4().hex[:12]
    if (
        not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", task_id)
        or task_id in known
        or task_id in doc.metadata.get("task-archive", {})
    ):
        raise LbError(
            "task ID must be unique, 1-64 letters/digits/_/-, starting with a letter",
            EXIT_USAGE,
        )
    item = {
        "id": task_id,
        "basis": "identity registration; historical evidence remains unknown",
    }
    nl = "\r\n" if b"\r\n" in doc.data else "\n"
    prefix = "" if doc.text[: target.end].endswith("\n") else nl
    records.put(doc, "task", item)
    changed = (
        doc.text[: target.end]
        + prefix
        + "    "
        + f"<!-- lb-task {task_id} -->"
        + nl
        + doc.text[target.end :]
    )
    return save(doc, changed, dry_run, task_id=task_id)


def show(root, log, task_id):
    doc = load(root, log)
    task, _, item = identity.lookup(doc, task_id)
    return Result({"task": identity.snapshot(task, item), "version_token": doc.token})


def migrate(root, log, token, dry_run):
    from logbook_cli.edit import task_content_end

    doc = writable(root, log, token)
    known = identity.bindings(doc)
    graph = {
        key: identity.dependencies(task, item) for key, (task, _, item) in known.items()
    }
    visiting, visited = set(), set()

    def visit(key):
        if key in visiting:
            raise LbError("legacy dependency cycle", EXIT_REFUSED)
        if key not in graph:
            raise LbError("missing legacy dependency: " + key, EXIT_REFUSED)
        if key in visited:
            return
        deps = graph[key]
        if not isinstance(deps, list) or any(not isinstance(d, str) for d in deps):
            raise LbError("invalid legacy dependencies", EXIT_REFUSED)
        visiting.add(key)
        for dependency in deps:
            visit(dependency)
        visiting.remove(key)
        visited.add(key)

    for key in graph:
        visit(key)
    mappings = []
    edits = []
    for task, _, item in identity.bindings(doc).values():
        if not ({"status"} | identity.LEGACY_REFERENCES).intersection(item):
            continue
        if (
            not identity.snapshot(task, item)["consistent"]
            or task.effective_state == "unknown"
        ):
            raise LbError(
                "ambiguous or conflicting legacy Task; resolve canonical facts explicitly before migration",
                EXIT_REFUSED,
            )
        if any(k in item for k in ("owner", "parent", "parent_id")):
            raise LbError(
                "legacy references require explicit canonical mapping before migration",
                EXIT_REFUSED,
            )
        mappings.append(
            {
                "id": item["id"],
                "from": item.get("status", task.effective_state),
                "to": task.effective_state,
            }
        )
        migrated = canonical_record(item)
        if "depends_on" in item:
            deps = item["depends_on"]
            if not isinstance(deps, list) or any(
                not isinstance(d, str)
                or d not in identity.bindings(doc)
                or d == item["id"]
                for d in deps
            ):
                raise LbError("invalid legacy dependencies", EXIT_REFUSED)
            current = identity.dependencies(task)
            if current and current != deps:
                raise LbError("conflicting legacy dependencies", EXIT_REFUSED)
            if deps and not current:
                end = task_content_end(doc, task)
                at = doc.offsets[end] + len(doc.lines[end])
                nl = "\r\n" if b"\r\n" in doc.data else "\n"
                edits.append((at, "    - Depends: " + ", ".join(deps) + nl))
            migrated.pop("depends_on")
        records.put(doc, "task", migrated)
    changed = doc.text
    for at, addition in sorted(edits, reverse=True):
        changed = changed[:at] + addition + changed[at:]
    from logbook_cli.task_records import migrate_inline

    revised = parse_text(changed.encode(), doc.path, doc.root, source=doc)
    changed = migrate_inline(revised, mappings)
    try:
        return save(doc, changed, dry_run, mappings=mappings)
    except OSError as exc:
        raise LbError(
            "migration interrupted; inspect log recover: " + str(exc), EXIT_REFUSED
        ) from exc


def canonical_record(item):
    value = {k: v for k, v in item.items() if k != "status"}
    if ({"status"} | identity.LEGACY_REFERENCES).intersection(item):
        value["history"] = [
            *item.get("history", []),
            {k: v for k, v in item.items() if k != "history"},
        ]
    return value


def semantic_transition(
    root, log, task_id, action, basis, token, dry_run, reason=None, to=None
):
    from logbook_cli.edit import task_content_end
    from logbook_cli.models import Field

    doc = writable(root, log, token)
    task, _, old = identity.lookup(doc, task_id)
    records.single_line(basis, "basis")
    identity.require_migrated_references(old)
    if (
        "status" in old
        and task.state != "!"
        and not identity.snapshot(task, old)["consistent"]
    ):
        raise LbError(
            "conflicting legacy state requires explicit migration", EXIT_REFUSED
        )
    if task.human and not (action == "start" and task.effective_state == "pending"):
        raise LbError("human-owned task transitions are protected", EXIT_REFUSED)
    from logbook_cli.task_records import require_current, resolution_text

    require_current(task, old)
    if any(a.kind in {Field.RESUME, Field.RESOLUTION} for a in task.annotations) and (
        any(a.kind is Field.RESUME for a in task.annotations)
        or (task.resolution and "resolution" not in old)
    ):
        raise LbError("inline task records require explicit task migrate", EXIT_REFUSED)
    item = canonical_record(old)
    state = task.effective_state
    allowed = {
        "complete": {"pending", "active"},
        "pause": {"pending", "active", "blocked"},
        "resume": {"pause"},
        "block": {"pending", "active"},
        "unblock": {"blocked"},
        "start": {"pending"},
        "cancel": {"pending", "active", "blocked", "pause"},
        "reopen": {"done", "cancelled"}
        | ({"active"} if old.get("status") == "submitted" else set()),
    }
    if state not in allowed[action]:
        raise LbError(f"cannot {action} a {state} task", EXIT_REFUSED)
    if action in {"start", "complete"}:
        for dep in identity.dependencies(task, old):
            predecessor, _, _ = identity.lookup(doc, dep)
            if predecessor.effective_state != "done":
                raise LbError("hard dependency is not done: " + dep, EXIT_REFUSED)
    remove = set()
    notes = []
    marker = task.state
    if action == "complete":
        marker = "x"
    elif action in {"start", "reopen"}:
        marker = "/"
        if action == "reopen":
            remove = {Field.RESOLUTION, Field.BLOCKER, Field.RESUME}
    elif action == "block":
        records.single_line(reason, "reason")
        notes.append("Blocker: " + reason)
    elif action == "unblock":
        remove.add(Field.BLOCKER)
    elif action == "pause":
        marker = "!"
        remove.add(Field.RESUME)
        item["resume"] = "pending" if task.state == " " else "active"
    elif action == "resume":
        if to is not None and "resume" in item and to != item["resume"]:
            raise LbError("--to conflicts with recorded prior state", EXIT_REFUSED)
        destination = item.get("resume", to)
        if destination not in {"pending", "active"}:
            raise LbError(
                "resume needs known prior state or --to pending|active", EXIT_REFUSED
            )
        marker = " " if destination == "pending" else "/"
        remove.add(Field.RESUME)
        item.pop("resume", None)
    elif action == "cancel":
        marker = "-"
        remove.add(Field.RESOLUTION)
        item.pop("resume", None)
        item["resolution"] = {
            "task": task.identity,
            "as": "cancelled",
            "decision": basis,
            "note": "Cancelled by Captain",
            "actor": "captain",
            "source": basis,
        }
        notes.append("Resolution: " + resolution_text(item["resolution"]))
    lines = list(doc.lines)
    nl = "\r\n" if b"\r\n" in doc.data else "\n"
    at = task.state_at - doc.offsets[task.line - 1]
    lines[task.line - 1] = (
        lines[task.line - 1][:at]
        + marker
        + lines[task.line - 1][at + len(task.state) :]
    )
    end = task_content_end(doc, task)
    for a in task.annotations:
        if a.kind in remove:
            lines[a.line - 1] = (
                "    - Historical disposition: " + a.value + nl
                if a.kind is Field.RESOLUTION and action == "reopen"
                else ""
            )
    lines[end] = (
        lines[end].rstrip("\r\n") + nl + "".join("    - " + note + nl for note in notes)
    )
    item["history"] = [
        *item.get("history", []),
        {
            "action": action,
            "previous": state,
            "basis": basis,
            "at": datetime.now(timezone.utc).isoformat(),
            "previous_record": {k: v for k, v in old.items() if k != "history"},
            "previous_annotations": [
                a.value for a in task.annotations if a.kind in remove
            ],
        },
    ]
    if action == "reopen":
        item.pop("acceptance", None)
        item.pop("submission", None)
        item.pop("resolution", None)
        item.pop("resume", None)
    records.put(doc, "task", item)
    changed = "".join(lines)
    revised = parse_text(changed.encode(), doc.path, doc.root, source=doc)
    result_task, _, _ = identity.lookup(revised, task_id)
    return save(
        doc, changed, dry_run, task_id=task_id, status=result_task.effective_state
    )


def transition(
    root, log, task_id, action, basis, token, dry_run, input_file=None, candidate=None
):
    doc = writable(root, log, token)
    records.read(doc, "task", require_closed=True)
    task, index, old = identity.lookup(doc, task_id)
    if action in {"cancel", "reopen"}:
        return semantic_transition(root, log, task_id, action, basis, token, dry_run)
    canonical = "status" not in old
    if canonical:
        if action == "start":
            return semantic_transition(
                root, log, task_id, action, basis, token, dry_run
            )
        old = {
            **old,
            "status": "submitted"
            if old.get("submission") and task.effective_state == "active"
            else {"done": "accepted"}.get(task.effective_state, task.effective_state),
        }
    records.single_line(basis, "basis")
    if action == "start":
        if task.effective_state != "pending":
            raise LbError("task is not pending", EXIT_REFUSED)
        for dep in identity.dependencies(task, old):
            predecessor, _, _ = identity.lookup(doc, dep)
            if predecessor.effective_state != "done":
                raise LbError("hard dependency is not done: " + dep, EXIT_REFUSED)
    view = identity.snapshot(task, old)
    if not view["consistent"]:
        raise LbError(
            "task metadata and checkbox disagree; reconcile human edits first",
            EXIT_REFUSED,
        )
    if task.human and not (action == "start" and old["status"] == "pending"):
        raise LbError("human-owned task transitions are protected", EXIT_REFUSED)
    transitions = {
        "start": ({"pending"}, "active"),
        "record-result": ({"active", "submitted"}, "submitted"),
        "accept": ({"submitted"}, "accepted"),
    }
    allowed, status = transitions[action]
    if old["status"] not in allowed:
        raise LbError(f"cannot {action} a {old['status']} task", EXIT_REFUSED)
    item = {
        **old,
        "status": status,
        "basis": basis,
        "at": datetime.now(timezone.utc).isoformat(),
        "history": [
            *old.get("history", []),
            {k: v for k, v in old.items() if k != "history"},
        ],
    }
    if action == "record-result":
        try:
            data = json.loads(safe_path(doc.root, input_file).read_text())
            if not isinstance(data, dict) or set(data) != {"candidate", "evidence"}:
                raise ValueError(
                    'result requires {"candidate":"identity", "evidence":["reference"]}'
                )
            records.single_line(data["candidate"], "candidate")
            if not isinstance(data["evidence"], list) or not data["evidence"]:
                raise ValueError("evidence must be a nonempty reference array")
            for ref in data["evidence"]:
                records.single_line(ref, "evidence")
        except (ValueError, TypeError) as exc:
            raise LbError(str(exc), EXIT_USAGE) from exc
        item["submission"] = {**data, "criteria_digest": identity.criteria(task)}
    if action == "accept":
        if not view["evidence_applicable"] or candidate != old.get(
            "submission", {}
        ).get("candidate"):
            raise LbError(
                "acceptance requires the current submitted candidate and applicable evidence",
                EXIT_REFUSED,
            )
        item["acceptance"] = {"candidate": candidate, "basis": basis}
    changed = identity.replace(
        doc, index, canonical_record(item) if canonical else item
    )
    changed = (
        changed[: task.state_at]
        + identity.TASK_STATES[status]
        + changed[task.state_at + 1 :]
    )
    return save(
        doc,
        changed,
        dry_run,
        task_id=task_id,
        status=status,
        effect="task transition only; no dispatch or business execution",
    )
