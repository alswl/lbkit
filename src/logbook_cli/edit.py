"""Pure text edits for an already parsed logbook task."""

from __future__ import annotations

import json
from collections import Counter

from logbook_cli.document import (
    EXIT_REFUSED,
    EXIT_USAGE,
    Document,
    LbError,
    Stage,
    Task,
    check,
    find_task,
    parse_text,
)
from logbook_cli.format import (
    ALARM_MARKER,
    NOTE_KINDS,
    SUMMARY_TEXT,
    field_value,
    prefix,
)
from logbook_cli.models import Field

ADVISORY_ISSUES = {
    "STAGE_EMOJI",
    "SKIPPED_EXPLICIT",
    "LINK_UNVERIFIED",
    "LOCAL_LINK_UNVERIFIED",
}


def introduced_issues(doc: Document, changed: str) -> list[dict]:
    """Find deterministic new problems without re-reporting historical ones."""
    candidate = parse_text(changed.encode("utf-8"), doc.path, doc.root)

    def identity(item: dict) -> tuple[str, str]:
        message = item["message"]
        if item["code"] == "DUPLICATE_TASK_TEXT":
            message = message.partition(" (lines ")[0]
        return item["code"], message

    before = Counter(
        identity(item) for item in check(doc) if item["code"] not in ADVISORY_ISSUES
    )
    introduced = []
    for item in check(candidate):
        if item["code"] in ADVISORY_ISSUES:
            continue
        key = identity(item)
        if before[key]:
            before[key] -= 1
        else:
            introduced.append(item)
    return introduced


def require_valid_candidate(doc: Document, changed: str) -> None:
    issues = introduced_issues(doc, changed)
    if issues:
        codes = ", ".join(sorted({item["code"] for item in issues}))
        raise LbError(f"candidate introduces check issue(s): {codes}", EXIT_REFUSED)


def task_content_end(doc: Document, task: Task) -> int:
    """Return the final physical line belonging to a task's indented body."""
    last = task.line - 1
    for index in range(task.line, len(doc.lines)):
        line = doc.lines[index]
        if not line.strip():
            continue
        if not line.startswith((" ", "\t")):
            break
        last = index
    return last


def append_note(
    doc: Document, task: Task, note: str, kind: str | None = None
) -> tuple[str, int]:
    """Append one child line after the task's existing indented content."""
    if task.human:
        raise LbError("refusing to add a note to a human-owned task", EXIT_REFUSED)
    if not note.strip() or "\n" in note or "\r" in note:
        raise LbError("task note must be one nonempty line", EXIT_USAGE)
    if kind is not None:
        if kind not in NOTE_KINDS:
            raise LbError(
                f"note kind must be one of: {', '.join(NOTE_KINDS)}", EXIT_USAGE
            )
        parsed_kind = field_value(kind + ":")
        assert parsed_kind is not None
        key = parsed_kind[0]
        alarm = ALARM_MARKER + " " if note.startswith(ALARM_MARKER + " ") else ""
        body = note[len(alarm) :]
        value = field_value(body)
        if not value or value[0] is not key:
            note = alarm + prefix(key, doc.locale) + body

    last = task_content_end(doc, task)

    existing = [line.strip() for line in doc.lines[task.line : last + 1]]
    if f"- {note}" in existing:
        raise LbError(
            "task note already exists; reread the task before appending", EXIT_REFUSED
        )

    at = doc.offsets[last] + len(doc.lines[last])
    newline = "\r\n" if b"\r\n" in doc.data else "\n"
    separator = "" if doc.text[:at].endswith(("\n", "\r")) else newline
    changed = doc.text[:at] + f"{separator}    - {note}{newline}" + doc.text[at:]
    return changed, last + 2


def add_task(
    doc: Document,
    stage_name: str,
    text: str,
    before_line: int | None = None,
    before_task: str | None = None,
) -> tuple[str, int]:
    """Add one unchecked task within one delivery stage at a task boundary."""
    if not text.strip() or text != text.strip() or "\n" in text or "\r" in text:
        raise LbError(
            "task text must be one nonempty line without outer whitespace", EXIT_USAGE
        )
    if text.startswith(("- [", "* [", "+ [")):
        raise LbError("--text is task text only, without a checkbox", EXIT_USAGE)
    stages = [
        stage for stage in doc.stages if stage.title == stage_name and stage.is_delivery
    ]
    if len(stages) != 1:
        raise LbError("delivery stage does not match uniquely", EXIT_REFUSED)
    stage: Stage = stages[0]
    if any(task.text == text for task in stage.tasks):
        raise LbError("task text already exists in this stage", EXIT_REFUSED)
    newline = "\r\n" if b"\r\n" in doc.data else "\n"

    if before_task is not None:
        before_line = find_task(doc, stage_name, before_task).line
    if before_line is not None:
        target = next((task for task in stage.tasks if task.line == before_line), None)
        if target is None:
            raise LbError(
                "--before-line must identify a task in the selected stage", EXIT_REFUSED
            )
        at = target.start
        line = target.line
    elif stage.tasks:
        last = task_content_end(doc, stage.tasks[-1])
        at = doc.offsets[last] + len(doc.lines[last])
        line = last + 2
    else:
        next_stage = next((item for item in doc.stages if item.line > stage.line), None)
        stop = next_stage.line - 1 if next_stage else len(doc.lines)
        headings = [
            index
            for index in range(stage.line, stop)
            if (value := field_value(doc.lines[index])) and value[0] is Field.TODO
        ]
        if len(headings) != 1:
            raise LbError(
                "empty stage needs one Todo field before a task can be added",
                EXIT_REFUSED,
            )
        index = headings[0]
        at = doc.offsets[index] + len(doc.lines[index])
        line = index + 2

    separator = "" if doc.text[:at].endswith(("\n", "\r")) else newline
    changed = doc.text[:at] + f"{separator}- [ ] {text}{newline}" + doc.text[at:]
    return changed, line


def single_line(value: str, label: str) -> None:
    if not value.strip() or value != value.strip() or "\n" in value or "\r" in value:
        raise LbError(
            f"{label} must be one nonempty line without outer whitespace", EXIT_USAGE
        )


def rewrite_task(doc: Document, task: Task, text: str, decision: str) -> str:
    single_line(text, "task text")
    single_line(decision, "decision")
    if task.human or task.state not in (" ", "/"):
        raise LbError(
            "only unfinished agent tasks may be rewritten; reopen and reverify completed results separately",
            EXIT_REFUSED,
        )
    if text.startswith(("- [", "* [", "+ [")):
        raise LbError("--text is task text only, without a checkbox", EXIT_USAGE)
    start = task.state_at + 3
    changed = doc.text[:start] + text + doc.text[start + len(task.text) :]
    candidate = parse_text(changed.encode("utf-8"), doc.path, doc.root)
    updated = find_task(candidate, task.stage, text)
    if (
        updated.human
        or updated.repositories != task.repositories
        or updated.preflight_blocker
    ):
        raise LbError(
            "rewrite must preserve agent ownership and repositories, and cannot introduce a preflight gate",
            EXIT_REFUSED,
        )
    changed, _ = append_note(
        candidate,
        updated,
        prefix(Field.STATUS, doc.locale)
        + SUMMARY_TEXT[doc.locale]["rewrite"]
        + decision,
    )
    return changed


def resolve_task(
    doc: Document, task: Task, disposition: str, decision: str, note: str
) -> str:
    single_line(decision, "decision")
    single_line(note, "note")
    if task.state != "-" or task.resolution or task.resolution_error:
        raise LbError(
            "resolve requires an unresolved [-] task without an existing disposition record",
            EXIT_REFUSED,
        )
    record = json.dumps(
        {"task": task.identity, "as": disposition, "decision": decision, "note": note},
        ensure_ascii=False,
    ).replace("<", "\\u003c")
    last = task_content_end(doc, task)
    at = doc.offsets[last] + len(doc.lines[last])
    newline = "\r\n" if b"\r\n" in doc.data else "\n"
    separator = "" if doc.text[:at].endswith(("\n", "\r")) else newline
    return (
        doc.text[:at]
        + separator
        + "    - "
        + prefix(Field.RESOLUTION, doc.locale)
        + record
        + newline
        + doc.text[at:]
    )
