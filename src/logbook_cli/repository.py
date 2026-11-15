"""Markdown authority and explicit one-way projection synchronization."""

from __future__ import annotations

import hashlib

from logbook_cli import records, state, unified
from logbook_cli.document import EXIT_REFUSED, LbError, parse_text, root_path, safe_path
from logbook_cli.models import Field


def source_digest(data):
    return hashlib.sha256(data).hexdigest()


def markdown_document(data, path, root):
    doc = parse_text(data, path, root)
    doc.markdown_authority = True
    import re

    doc.metadata["task-archive"] = {
        key: {"id": key}
        for key in re.findall(
            r"^### Archived Task ([A-Za-z][A-Za-z0-9_-]{0,63})$", doc.text, re.M
        )
    }
    for stage in doc.stages:
        for task in stage.tasks:
            resolutions = [
                a.value for a in task.annotations if a.kind is Field.RESOLUTION
            ]
            if resolutions:
                match = re.fullmatch(
                    r"(cancelled|human-cancelled|not-applicable): (.+?) — (.+)",
                    resolutions[0],
                )
                if len(resolutions) != 1 or not match or task.state != "-":
                    task.resolution_error = True
                else:
                    task.resolution = {
                        "task": task.identity,
                        "as": match[1],
                        "decision": match[2],
                        "note": match[3],
                    }
                    task.resolution_error = False
    return doc


def project_document(data, path, root):
    from logbook_cli.task_identity import bindings, dependencies

    doc = markdown_document(data, path, root)
    records.anchors(doc, require_closed=True)
    from logbook_cli.document import h1_count
    if h1_count(doc) != 1 or any(stage.unknown_task_lines for stage in doc.stages):
        raise LbError('invalid document structure or task marker', EXIT_REFUSED)
    known = bindings(doc)
    if set(known).intersection(doc.metadata.get('task-archive', {})):
        raise LbError('archived Task ID cannot be reused', EXIT_REFUSED)
    all_tasks = [t for s in doc.stages for t in s.tasks]
    if len(all_tasks) != len(known):
        raise LbError("identity_missing: identify every task before sync", EXIT_REFUSED)
    graph = {key: dependencies(task) for key, (task, _, _) in known.items()}
    active, done = set(), set()

    def visit(key):
        if key in active or key not in graph:
            raise LbError(
                "invalid dependency cycle or missing task: " + key, EXIT_REFUSED
            )
        if key in done:
            return
        active.add(key)
        for dep in graph[key]:
            visit(dep)
        active.remove(key)
        done.add(key)

    tasks = {}
    for key, (task, _, _) in known.items():
        visit(key)
        if task.resolution_error or task.effective_state == "unknown":
            raise LbError(
                "invalid readable task state at line " + str(task.line), EXIT_REFUSED
            )
        resume = [a.value for a in task.annotations if a.kind is Field.RESUME]
        if resume and (
            len(resume) != 1
            or resume[0] not in {"pending", "active"}
            or task.state != "!"
        ):
            raise LbError("invalid readable Resume", EXIT_REFUSED)
        tasks[key] = {
            "id": key,
            "stage": task.stage,
            "text": task.text,
            "checkbox": task.state,
            "effective_state": task.effective_state,
            "conditions": [
                a.value for a in task.annotations if a.kind is Field.ACCEPTANCE
            ],
            "dependencies": graph[key],
            "artifact_refs": artifact_refs(task),
            "line": task.line,
        }
    return {
        "source_digest": source_digest(data),
        "stages": [s.title for s in doc.stages],
        "tasks": tasks,
    }


def artifact_refs(task):
    from logbook_cli.document import LINK_RE

    refs = []
    for annotation in task.annotations:
        if annotation.kind is Field.ARTIFACT:
            links = [match[1] for match in LINK_RE.findall(annotation.value)]
            refs.extend(links or [annotation.value.strip()])
    return list(dict.fromkeys(refs))


def sync_status(doc, value):
    projection = (
        (value or {}).get("documents", {}).get(state.section(doc.path, doc.root))
    )
    return (
        "missing"
        if projection is None
        else (
            "synced"
            if projection.get("source_digest") == source_digest(doc.data)
            else "stale"
        )
    )


def read_document(root, log):
    base = root_path(str(root))
    path = safe_path(base, str(log))
    doc = markdown_document(path.read_bytes(), path, base)
    _, value = unified.locate(base, path)
    doc.sync_status = sync_status(doc, value)
    if value:
        doc.metadata["document"] = {
            "identity": {"id": "identity", "uuid": value["identity"]["run_id"]}
        }
    return doc


def sync_document(root, log, dry_run=False):
    base = root_path(str(root))
    path = safe_path(base, str(log))
    with unified.writer(base, path, dry_run):
        target, value = unified.locate(base, path, required=True)
        data = path.read_bytes()
        candidate = project_document(data, path, base)
        key = state.section(path, base)
        prior = value["documents"].get(key, {})
        before_ids = set(prior.get("tasks", {}))
        after_ids = set(candidate["tasks"])
        changed = prior != candidate
        value["documents"][key] = candidate
        if changed and not dry_run:
            unified.publish(target, value)
        current = path.read_bytes()
        status = (
            (
                "missing"
                if not prior
                else (
                    "synced"
                    if prior.get("source_digest") == source_digest(current)
                    else "stale"
                )
            )
            if dry_run
            else ("synced" if current == data else "stale")
        )
        return {
            "changed": changed,
            "dry_run": dry_run,
            "sync_status": status,
            "source_digest": candidate["source_digest"],
            "added_task_ids": sorted(after_ids - before_ids),
            "removed_task_ids": sorted(before_ids - after_ids),
            "diagnostics": [],
        }


def require_synced(root, log, task_id):
    from logbook_cli.task_identity import lookup

    doc = read_document(root, log)
    task, _, _ = lookup(doc, task_id)
    if doc.sync_status != "synced":
        raise LbError(
            "sync_required: run log sync-state before Task execution", EXIT_REFUSED
        )
    return doc, task


def edit_document(doc, changed, dry_run=False):
    from logbook_cli.storage import replace_bytes_at

    candidate = markdown_document(changed.encode(), doc.path, doc.root)
    records.anchors(candidate, require_closed=True)
    if not dry_run and changed.encode() != doc.data:
        with unified.writer(doc.root, doc.path):
            if doc.path.read_bytes() != doc.data:
                raise LbError(
                    "document changed during edit; reread before applying semantic change",
                    EXIT_REFUSED,
                )
            fd = __import__("os").open(
                doc.path.parent,
                __import__("os").O_RDONLY | __import__("os").O_DIRECTORY,
            )
            try:
                replace_bytes_at(fd, doc.path.name, changed.encode(), doc.data)
            finally:
                __import__("os").close(fd)
    return {
        "document_saved": not dry_run and changed != doc.text,
        "sync_required": changed != doc.text
        or getattr(doc, "sync_status", "missing") != "synced",
        "dry_run": dry_run,
    }
