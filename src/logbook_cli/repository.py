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


def project_document(data, path, root, *, reserved_archive_ids=(), dependency_graph=None):
    from logbook_cli.services.dependencies import validate
    from logbook_cli.task_identity import bindings, task_dependencies

    doc = markdown_document(data, path, root)
    records.anchors(doc, require_closed=True)
    from logbook_cli.document import h1_count
    if h1_count(doc) != 1 or any(stage.unknown_task_lines for stage in doc.stages):
        raise LbError('invalid document structure or task marker', EXIT_REFUSED)
    known = bindings(doc)
    if set(known).intersection(set(doc.metadata.get("task-archive", {})) | set(reserved_archive_ids)):
        raise LbError('archived Task ID cannot be reused', EXIT_REFUSED)
    all_tasks = [t for s in doc.stages for t in s.tasks]
    if len(all_tasks) != len(known):
        raise LbError("identity_missing: identify every task before sync", EXIT_REFUSED)
    graph = (
        {key: task_dependencies(doc, task, item) for key, (task, _, item) in known.items()}
        if dependency_graph is None
        else dependency_graph
    )
    validate(graph)

    tasks = {}
    for key, (task, _, _) in known.items():
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
            "artifact_refs": artifact_refs(task),
            "line": task.line,
        }
        if dependency_graph is None:
            tasks[key]["dependencies"] = graph[key]
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


def imported_archive_ids(value):
    history = list(value.get("legacy_history", {}).values())
    history.extend(
        projection.get("legacy_metadata", {})
        for projection in value["documents"].values()
        if isinstance(projection, dict)
    )
    return {
        key
        for groups in history
        if isinstance(groups, dict) and isinstance(groups.get("task-archive"), dict)
        for key in groups["task-archive"]
    }


def event_context(run, document):
    """Version the event stream together with its exact companion association."""
    return unified.encode({
        "run_id": run["identity"]["run_id"],
        "document": document,
        "events": run.get("run_events", {}).get(document, []),
    })


def read_document(root, log, *, load_dependencies=True):
    base = root_path(str(root))
    path = safe_path(base, str(log))
    doc = markdown_document(path.read_bytes(), path, base)
    target, value = unified.locate(base, path)
    doc.sync_status = sync_status(doc, value)
    if value:
        key = state.section(path, base)
        doc.unified_state_path = target
        if load_dependencies and "dependency_source" in value and key == value["identity"]["log_path"]:
            from logbook_cli.services.dependencies import load

            doc.task_dependency_graph = load(doc, target, value)
            if state.read_regular(base, path) != doc.data:
                raise LbError("Logbook changed during dependency read; reread", EXIT_REFUSED)
        doc.legacy_metadata = value["documents"].get(key, {}).get("legacy_metadata", {})
        doc.legacy_history = value.get("legacy_history", {}).get(key, {})
        if key != value["identity"]["log_path"]:
            doc.run_events = value.get("run_events", {}).get(key, [])
            doc.run_event_context = event_context(value, key)
        if "legacy_migration" in value:
            doc.migration_plan = value["legacy_migration"]["plan_token"]
        doc.metadata["task-archive"].update(
            (archive_id, {"id": archive_id})
            for archive_id in imported_archive_ids(value)
        )
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
        key = state.section(path, base)
        graph = None
        if "dependency_source" in value and key == value["identity"]["log_path"]:
            from logbook_cli.services.dependencies import load

            graph = load(markdown_document(data, path, base), target, value)
        candidate = project_document(
            data,
            path,
            base,
            reserved_archive_ids=imported_archive_ids(value),
            dependency_graph=graph,
        )
        prior = value["documents"].get(key, {})
        if "legacy_metadata" in prior:
            candidate["legacy_metadata"] = prior["legacy_metadata"]
        before_ids = set(prior.get("tasks", {}))
        after_ids = set(candidate["tasks"])
        changed = prior != candidate
        if changed and not dry_run:
            value["documents"][key] = candidate
            unified.publish_run(base, target, value)
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


def edit_document(doc, changed, dry_run=False, *, dependency_graph=None):
    from logbook_cli.services import dependencies, dependency_transaction

    candidate = markdown_document(changed.encode(), doc.path, doc.root)
    active_ids = {key for _, key in records.anchors(candidate, require_closed=True)}
    if active_ids.intersection(doc.metadata.get("task-archive", {})):
        raise LbError("archived Task ID cannot be reused", EXIT_REFUSED)
    if dependency_graph is not None:
        if set(dependency_graph) != active_ids:
            raise LbError("replacement graph must cover the current Task IDs", EXIT_REFUSED)
        dependencies.validate(dependency_graph)
    elif doc.task_dependency_graph is not None:
        validate_retained_graph(doc.task_dependency_graph, active_ids)
    if not dry_run and changed.encode() != doc.data:
        with unified.writer(doc.root, doc.path):
            target, current = unified.locate(doc.root, doc.path)
            if doc.migration_plan is not None:
                if (current or {}).get("legacy_migration", {}).get("plan_token") != doc.migration_plan:
                    raise LbError("document authority changed; reread before editing", EXIT_REFUSED)
            if state.read_regular(doc.root, doc.path) != doc.data:
                raise LbError(
                    "document changed during edit; reread before applying semantic change",
                    EXIT_REFUSED,
                )
            is_log = current and state.section(doc.path, doc.root) == current["identity"]["log_path"]
            if dependency_graph is not None and not is_log:
                raise LbError("replace dependencies on the Run Logbook", EXIT_REFUSED)
            if is_log and ("dependency_source" in current or dependency_graph is not None):
                original = markdown_document(doc.data, doc.path, doc.root)
                graph = dependencies.load(original, target, current)
                original.task_dependency_graph = doc.task_dependency_graph
                if graph != dependencies.effective(original):
                    raise LbError("Task dependencies changed; reread before editing", EXIT_REFUSED)
                if dependency_graph is None:
                    validate_retained_graph(graph, active_ids)
            if dependency_graph is None:
                dependency_transaction.replace_file(
                    doc.root, doc.path, changed.encode(), doc.data
                )
            else:
                from logbook_cli.services.readiness import unresolved_operation

                runtime = current["execution"]
                if any(
                    runtime["tasks"].get(task_id, {}).get("current_binding_id")
                    or unresolved_operation(runtime, task_id)
                    for task_id in set(graph) - active_ids
                ):
                    raise LbError("resolve in-flight binding before replacement", EXIT_REFUSED)
                if "dependency_source" not in current:
                    dependencies.stage_cutover(original, target, current)
                    unified.publish(target, current)
                dependency_transaction.publish(
                    doc, target, current["identity"]["run_id"], changed, dependency_graph
                )
    return {
        "document_saved": not dry_run and changed != doc.text,
        "sync_required": changed != doc.text
        or getattr(doc, "sync_status", "missing") != "synced",
        "dry_run": dry_run,
    }


def validate_retained_graph(graph, active_ids):
    from logbook_cli.services import dependencies

    if any(edges for key, edges in graph.items() if key not in active_ids):
        raise LbError("Task removal requires its dependency update", EXIT_REFUSED)
    dependencies.validate({key: graph.get(key, []) for key in active_ids})
