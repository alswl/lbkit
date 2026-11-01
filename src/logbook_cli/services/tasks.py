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
    paths = [safe_path(base, log)] if log else discover(base, projects_dir)
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
    root: str, log: str, stage: str, task: str, status: str, token: str, dry_run: bool
) -> Result:
    doc = writable(root, log, token)
    item = find_task(doc, stage, task)
    from logbook_cli.task_identity import bindings

    if any(t.line == item.line for t, _, _ in bindings(doc).values()):
        raise LbError(
            "identified task: use semantic lifecycle actions such as start/complete/pause/resume/cancel/reopen",
            EXIT_REFUSED,
        )
    if item.human and not (item.status is TaskState.TODO and status == "/"):
        raise LbError(
            "refusing to change a human-owned task checkbox except from not-started to in-progress",
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
) -> Result:
    doc = writable(root, log, token)
    changed, line = append_note(
        doc, find_task(doc, stage, task), text, kind, replace_line
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
) -> Result:
    doc = writable(root, log, token)
    item = find_task(doc, stage, task)
    return save(
        doc,
        rewrite_task(doc, item, text, decision, assign_repo),
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

    doc = writable(root, log, token)
    records.single_line(decision, "decision")
    try:
        request = json.loads(safe_path(doc.root, input_file).read_text())
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
    if any(
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
    affected = {
        i
        for i, (t, _, _) in known.items()
        if record["id"] in task_identity.dependencies(t)
    }
    if set(mapping) != affected:
        raise LbError(
            "reference map must name every affected live task exactly once",
            EXIT_REFUSED,
        )
    graph = {
        i: task_identity.dependencies(t)
        for i, (t, _, _) in known.items()
        if i != record["id"]
    }
    graph.update({i: task_identity.dependencies(old) for i in ids})
    for i, deps in mapping.items():
        if (
            not isinstance(deps, list)
            or not deps
            or any(not isinstance(d, str) or d not in graph for d in deps)
        ):
            raise LbError("invalid replacement dependency mapping", EXIT_REFUSED)
        if not set(task_identity.dependencies(known[i][0])) - {record["id"]} <= set(
            deps
        ):
            raise LbError("mapping must preserve unrelated dependencies", EXIT_REFUSED)
        graph[i] = deps
    visiting, visited = set(), set()

    def visit(i):
        if i in visiting:
            raise LbError("dependency cycle", EXIT_REFUSED)
        if i not in graph:
            raise LbError("missing dependency: " + i, EXIT_REFUSED)
        if i in visited:
            return
        visiting.add(i)
        for dep in graph[i]:
            visit(dep)
        visiting.remove(i)
        visited.add(i)

    for i in graph:
        visit(i)
    nl = "\r\n" if b"\r\n" in doc.data else "\n"
    edits = []
    for i in affected:
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
        if graph[r["id"]]:
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
    return save(doc, changed, dry_run, replacement_ids=ids, reference_changes=mapping)


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
