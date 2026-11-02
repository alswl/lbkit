"""Task machine facts in the existing document state, with readable projections."""

import uuid

from logbook_cli import records
from logbook_cli.document import EXIT_REFUSED, LbError
from logbook_cli.models import Field


def resolution_text(value):
    text = f"{value['as']}: {value['decision']} — {value['note']}"
    return text.replace("<", "&lt;").replace(">", "&gt;")


def valid_resolution(value, task):
    return (
        isinstance(value, dict)
        and set(value)
        in (
            {"task", "as", "decision", "note"},
            {"task", "as", "decision", "note", "actor", "source"},
        )
        and value.get("task") == task.identity
        and isinstance(value.get("as"), str)
        and value.get("as") in {"cancelled", "human-cancelled", "not-applicable"}
        and all(
            isinstance(value.get(k), str)
            and value[k].strip()
            and not any(c in value[k] for c in "\r\n")
            for k in ("decision", "note")
        )
        and (
            value["as"] != "cancelled"
            or all(
                isinstance(value.get(k), str) and value[k].strip()
                for k in ("actor", "source")
            )
        )
        and task.state == "-"
    )


def hydrate(doc):
    from logbook_cli.task_identity import bindings

    try:
        bound = bindings(doc)
    except LbError:
        return  # The shared identity checker reports missing/duplicate/orphan state.
    for task, _, item in bound.values():
        value = item.get("resolution")
        if "resolution" not in item:
            continue
        annotations = [a.value for a in task.annotations if a.kind is Field.RESOLUTION]
        valid = valid_resolution(value, task) and annotations == [
            resolution_text(value)
        ]
        task.resolution = value if valid else None
        task.resolution_error = not valid


def require_current(task, item):
    if task.resolution_error:
        raise LbError("invalid, conflicting or stale task resolution", EXIT_REFUSED)
    prior = [a.value for a in task.annotations if a.kind is Field.RESUME]
    if prior and "resume" in item:
        raise LbError(
            "conflicting inline and stored Resume; reconcile explicitly", EXIT_REFUSED
        )
    if (
        (prior and (len(prior) != 1 or prior[0] not in {"pending", "active"}))
        or (
            "resume" in item
            and (
                not isinstance(item["resume"], str)
                or item["resume"] not in {"pending", "active"}
            )
        )
        or ((prior or "resume" in item) and task.state != "!")
    ):
        raise LbError("invalid or stale Resume state", EXIT_REFUSED)


def migrate_inline(doc, mappings):
    """Explicitly move validated legacy annotations, preserving exact originals."""
    from logbook_cli.task_identity import bindings

    known = {t.line: row for t, _, row in bindings(doc).values()}
    lines = list(doc.lines)
    nl = "\r\n" if b"\r\n" in doc.data else "\n"
    for stage in doc.stages:
        for task in stage.tasks:
            item = dict(known.get(task.line, {}))
            require_current(task, item)
            legacy = [
                a
                for a in task.annotations
                if a.kind is Field.RESUME
                or (a.kind is Field.RESOLUTION and "resolution" not in item)
            ]
            if not legacy:
                continue
            if "id" not in item:
                item["id"] = "task-" + uuid.uuid4().hex[:12]
                lines[task.line - 1] = (
                    lines[task.line - 1].rstrip("\r\n")
                    + nl
                    + f"    <!-- lb-task {item['id']} -->"
                    + nl
                )
            mappings.append(
                {
                    "id": item["id"],
                    "from": "inline",
                    "to": "lb/",
                    "fields": [a.kind.value for a in legacy],
                }
            )
            history = {"inline_annotations": [doc.lines[a.line - 1] for a in legacy]}
            for a in legacy:
                if a.kind is Field.RESOLUTION:
                    if task.resolution is None:
                        raise LbError("invalid legacy Resolution", EXIT_REFUSED)
                    item["resolution"] = task.resolution
                    history["resolution"] = task.resolution
                    lines[a.line - 1] = (
                        "    - "
                        + a.label
                        + ": "
                        + resolution_text(task.resolution)
                        + nl
                    )
                else:
                    item["resume"] = a.value
                    lines[a.line - 1] = ""
            item["history"] = [*item.get("history", []), history]
            records.put(doc, "task", item)
    return "".join(lines)
