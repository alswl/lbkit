"""Task use cases; independent of the command framework."""

from logbook_cli.document import (
    EXIT_REFUSED,
    EXIT_USAGE,
    LbError,
    context,
    discover,
    find_task,
    parse,
    root_path,
    safe_path,
)
from logbook_cli.edit import (
    add_task,
    append_note,
    resolve_task,
    rewrite_task,
    split_task,
)
from logbook_cli.format import CHECKBOX
from logbook_cli.models import TaskState
from logbook_cli.services.common import Result, load, save, writable
from logbook_cli.views import task_rows


def list_tasks(
    root: str,
    log: str | None,
    projects_dir: str,
    stage: str | None,
    status: str | None,
    human: bool,
) -> Result:
    base = root_path(root)
    paths = [safe_path(base, log, field="LOG")] if log else discover(base, projects_dir)
    states = {s.value: glyph for glyph, s in CHECKBOX.items()}
    return Result(
        [
            row
            for path in paths
            for row in task_rows(
                parse(path, base),
                stage=stage,
                state=states.get(status) if status else None,
                human=human,
            )
        ]
    )


def next_task(root: str, log: str) -> Result:
    return Result(context(load(root, log))["next_task"])


def depends(root, log, task_id, input_file, expect_route, dry_run=False):
    from dataclasses import replace

    from logbook_cli import state, unified
    from logbook_cli.services import dependencies
    from logbook_cli.services.agent_observation import _input
    from logbook_cli.services.route_scope import route_scope

    doc = load(root, log)
    if not doc.markdown_authority:
        raise LbError("dependency editing requires an initialized Run", EXIT_REFUSED)
    request = _input(doc, input_file)
    if not isinstance(request, dict) or set(request) != {"depends_on"}:
        raise LbError("dependency input requires depends_on", EXIT_USAGE)
    edges = request["depends_on"]
    if not isinstance(edges, list) or any(not isinstance(edge, str) for edge in edges):
        raise LbError("depends_on must be a list of Task IDs", EXIT_USAGE)
    with unified.writer(doc.root, doc.path, dry_run):
        doc = writable(root, log, None)
        target, run = unified.locate(doc.root, doc.path, required=True)
        if state.section(doc.path, doc.root) != run["identity"]["log_path"]:
            raise LbError("edit dependencies on the Run Logbook", EXIT_REFUSED)
        before = route_scope(doc)
        if before["route_ref"] != expect_route:
            raise LbError("route changed; reread before editing dependencies", EXIT_REFUSED)
        graph = dict(dependencies.effective(doc))
        if task_id not in graph:
            raise LbError("unknown dependency Task: " + task_id, EXIT_REFUSED)
        changed = graph[task_id] != edges
        graph[task_id] = edges
        dependencies.validate(graph)
        after = route_scope(replace(doc, task_dependency_graph=graph))
        if changed and not dry_run:
            if "dependency_source" not in run:
                dependencies.stage_cutover(doc, target, run)
                unified.publish(target, run)
            dependencies.replace_graph(doc, target, run, graph)
    return Result({
        "task_id": task_id,
        "dependencies": graph,
        "route_ref": after["route_ref"],
        "affected_task_scopes": sorted(
            key for key, scope in after["task_scopes"].items()
            if scope != before["task_scopes"].get(key)
        ),
        "changed": changed,
        "dry_run": dry_run,
    })


def add(
    root: str,
    log: str,
    stage: str,
    text: str,
    token: str,
    dry_run: bool,
    before_line: int | None,
    before_task: str | None,
) -> Result:
    if before_line is not None and before_task is not None:
        raise LbError(
            "--before-line and --before-task are mutually exclusive", EXIT_USAGE
        )
    doc = writable(root, log, token)
    changed, line = add_task(doc, stage, text, before_line, before_task)
    return save(doc, changed, dry_run, line=line)


def update(
    root: str,
    log: str,
    stage: str,
    task: str,
    status: str,
    token: str,
    dry_run: bool,
    confirmed: bool = False,
) -> Result:
    doc = writable(root, log, token)
    item = find_task(doc, stage, task)
    from logbook_cli.task_identity import bindings

    if any(t.line == item.line for t, _, _ in bindings(doc).values()):
        raise LbError(
            "identified task: use semantic lifecycle actions such as start/complete/pause/resume/cancel/reopen",
            EXIT_REFUSED,
        )
    if (
        item.human
        and not confirmed
        and not (item.status is TaskState.TODO and status == "/")
    ):
        raise LbError(
            "human-owned checkbox change requires --confirmed after explicit human confirmation; pending-to-active remains allowed",
            EXIT_REFUSED,
        )
    if status not in CHECKBOX:
        raise LbError("--status must be one of: space, /, x, -, !", EXIT_USAGE)
    changed = doc.text[: item.state_at] + status + doc.text[item.state_at + 1 :]
    return save(doc, changed, dry_run, line=item.line)


def note(
    root: str,
    log: str,
    stage: str,
    task: str,
    text: str,
    kind: str | None,
    token: str,
    dry_run: bool,
    replace_line: int | None = None,
    confirmed: bool = False,
) -> Result:
    doc = writable(root, log, token)
    changed, line = append_note(
        doc, find_task(doc, stage, task), text, kind, replace_line, confirmed=confirmed
    )
    return save(doc, changed, dry_run, line=line)


def rewrite(
    root: str,
    log: str,
    stage: str,
    task: str,
    text: str,
    decision: str,
    token: str,
    dry_run: bool,
    assign_repo: str | None = None,
    confirmed: bool = False,
) -> Result:
    doc = writable(root, log, token)
    item = find_task(doc, stage, task)
    return save(
        doc,
        rewrite_task(doc, item, text, decision, assign_repo, confirmed=confirmed),
        dry_run,
        line=item.line,
    )


def split(
    root: str,
    log: str,
    stage: str,
    task: str,
    texts: tuple[str, ...],
    decision: str,
    token: str,
    dry_run: bool,
) -> Result:
    doc = writable(root, log, token)
    item = find_task(doc, stage, task)
    from logbook_cli.task_identity import bindings

    if any(t.line == item.line for t, _, _ in bindings(doc).values()):
        raise LbError(
            "identified task: use --input-file with reference mappings", EXIT_REFUSED
        )
    # Keep the existing scope/ownership checks before archiving the original.
    candidate = split_task(doc, item, texts, decision)
    import uuid

    from logbook_cli import records
    from logbook_cli.document import parse_text
    from logbook_cli.edit import task_content_end
    from logbook_cli.task_identity import dependencies

    parsed = parse_text(candidate.encode(), doc.path, doc.root, source=doc)
    retired = find_task(parsed, stage, task)
    stop = task_content_end(parsed, retired)
    end = parsed.offsets[stop] + len(parsed.lines[stop])
    original_end = task_content_end(doc, item)
    replacement_ids: list[str] = []
    prerequisites = dependencies(item)
    # Assign stable new identities even when the original had no managed ID.
    for text in reversed(texts):
        replacement = find_task(parsed, stage, text)
        new_id = "task-" + uuid.uuid4().hex[:12]
        replacement_ids.insert(0, new_id)
        records.put(doc, "task", {"id": new_id})
        nl = "\r\n" if b"\r\n" in doc.data else "\n"
        dependency_note = (
            "    - Depends: " + ", ".join(prerequisites) + nl if prerequisites else ""
        )
        candidate = (
            candidate[: replacement.end]
            + "    <!-- lb-task "
            + new_id
            + " -->"
            + nl
            + dependency_note
            + candidate[replacement.end :]
        )
    records.put(
        doc,
        "task-archive",
        {
            "id": "task-" + uuid.uuid4().hex[:12],
            "previous_text": item.text,
            "previous_task_digest": item.identity,
            "content": "".join(doc.lines[item.line - 1 : original_end + 1]),
            "replacement_texts": list(texts),
            "replacement_ids": replacement_ids,
            "basis": decision,
        },
    )
    return save(
        doc,
        candidate[: retired.start] + candidate[end:],
        dry_run,
        original_task=item.identity,
        replacement_tasks=list(texts),
    )


def replace_bound(root, log, input_file, decision, token, dry_run):
    import json
    import re

    from logbook_cli import records, task_identity
    from logbook_cli.document import parse_text, safe_path
    from logbook_cli.edit import task_content_end
    from logbook_cli.models import Field
    from logbook_cli.services import dependencies

    doc = writable(root, log, token)
    records.single_line(decision, "decision")
    try:
        request = json.loads(safe_path(doc.root, input_file, field="--input-file").read_text())
        if set(request) != {"task_id", "replacements", "reference_changes"}:
            raise ValueError(
                "replacement requires task_id, replacements, reference_changes"
            )
        known = task_identity.bindings(doc)
        old, _, record = task_identity.lookup(doc, request["task_id"])
        replacements = request["replacements"]
        mapping = request["reference_changes"]
        if (
            not isinstance(replacements, list)
            or len(replacements) < 2
            or not isinstance(mapping, dict)
        ):
            raise ValueError(
                "replacement requires at least two tasks and a reference map"
            )
        ids = [r["id"] for r in replacements]
        if any(set(r) != {"id", "text"} for r in replacements):
            raise ValueError("replacement fields are id and text")
        if len(ids) != len(set(ids)) or any(
            not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", i)
            or i in known
            or i in doc.metadata.get("task-archive", {})
            for i in ids
        ):
            raise ValueError("replacement IDs must be new and unique")
    except (ValueError, TypeError, KeyError) as exc:
        raise LbError(str(exc), EXIT_REFUSED) from exc
    # Validate the old package and replacement scopes using the shared edit rules.
    split_task(doc, old, tuple(r["text"] for r in replacements), decision)
    for _, _, row in known.values():
        task_identity.require_migrated_references(row)
    identified_lines = {t.line for t, _, _ in known.values()}
    if doc.task_dependency_graph is None and any(
        t.line not in identified_lines and record["id"] in task_identity.dependencies(t)
        for stage in doc.stages
        for t in stage.tasks
    ):
        raise LbError(
            "identify every dependent task before replacement so references can be mapped",
            EXIT_REFUSED,
        )
    for kind in ("dispatch", "binding", "agent"):
        for row in doc.metadata.get(kind, {}).values():
            if row.get("task_id") == record["id"] and row.get("status") not in {
                "closed",
                "cancelled",
            }:
                raise LbError(
                    "resolve in-flight binding before replacement", EXIT_REFUSED
                )
    original_graph = dependencies.effective(doc)
    affected = {key for key, edges in original_graph.items() if record["id"] in edges}
    if set(mapping) != affected:
        raise LbError(
            "reference map must name every affected live task exactly once",
            EXIT_REFUSED,
        )
    graph = dict(original_graph)
    predecessors = graph.pop(record["id"])
    graph.update({i: predecessors for i in ids})
    for i, deps in mapping.items():
        if (
            not isinstance(deps, list)
            or not deps
            or any(not isinstance(d, str) or d not in graph for d in deps)
        ):
            raise LbError("invalid replacement dependency mapping", EXIT_REFUSED)
        if not set(original_graph[i]) - {record["id"]} <= set(deps):
            raise LbError("mapping must preserve unrelated dependencies", EXIT_REFUSED)
        graph[i] = deps
    dependencies.validate(graph)
    nl = "\r\n" if b"\r\n" in doc.data else "\n"
    edits = []
    for i in affected if not doc.markdown_authority else ():
        t = known[i][0]
        for a in t.annotations:
            if a.kind is Field.DEPENDS:
                at = doc.offsets[a.line - 1]
                edits.append((at, at + len(doc.lines[a.line - 1]), ""))
        end = task_content_end(doc, t)
        at = doc.offsets[end] + len(doc.lines[end])
        edits.append((at, at, "    - Depends: " + ", ".join(graph[i]) + nl))
    end = task_content_end(doc, old)
    stop = doc.offsets[end] + len(doc.lines[end])
    additions = ""
    for r in replacements:
        additions += f"- [ ] {r['text']}{nl}    <!-- lb-task {r['id']} -->{nl}"
        additions += (
            f"    - Source: Split from {record['id']}: {old.text}; "
            f"decision: {decision}; verify acceptance separately.{nl}"
        )
        if graph[r["id"]] and not doc.markdown_authority:
            additions += "    - Depends: " + ", ".join(graph[r["id"]]) + nl
    edits.append((old.start, stop, additions))
    changed = doc.text
    for start, stop, value in sorted(edits, reverse=True):
        changed = changed[:start] + value + changed[stop:]
    records.put(
        doc,
        "task-archive",
        {
            **record,
            "previous_text": old.text,
            "content": "".join(doc.lines[old.line - 1 : end + 1]),
            "replacement_ids": ids,
            "basis": decision,
        },
    )
    del doc.metadata["task"][record["id"]]
    for r in replacements:
        records.put(doc, "task", {"id": r["id"]})
    candidate = parse_text(changed.encode(), doc.path, doc.root, source=doc)
    task_identity.bindings(candidate)
    return save(
        doc, changed, dry_run,
        dependency_graph=graph if doc.markdown_authority else None,
        replacement_ids=ids, reference_changes=mapping,
    )


def resolve(
    root: str,
    log: str,
    stage: str,
    task: str,
    disposition: str,
    decision: str,
    note: str,
    token: str,
    dry_run: bool,
) -> Result:
    doc = writable(root, log, token)
    item = find_task(doc, stage, task)
    from logbook_cli.task_identity import bindings

    if any(t.line == item.line for t, _, _ in bindings(doc).values()):
        raise LbError(
            "identified task: use lifecycle actions; structural identity changes require an explicit migration",
            EXIT_REFUSED,
        )
    return save(
        doc,
        resolve_task(doc, item, disposition, decision, note),
        dry_run,
        line=item.line,
    )
