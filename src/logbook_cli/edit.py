"""Pure text edits for an already parsed logbook task."""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlparse

from logbook_cli.document import (
    EXIT_REFUSED,
    EXIT_USAGE,
    LINK_RE,
    Document,
    LbError,
    Stage,
    Task,
    check,
    find_task,
    parse_text,
    visible_lines,
)
from logbook_cli.format import (
    ALARM_MARKER,
    NOTE_KINDS,
    SUMMARY_TEXT,
    field_value,
    prefix,
    skill_chain,
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
    doc: Document,
    task: Task,
    note: str,
    kind: str | None = None,
    replace_line: int | None = None,
) -> tuple[str, int]:
    """Append one child line after the task's existing indented content."""
    if task.human and not (
        kind is not None and (field_value(kind + ":") or (None,))[0] is Field.STATUS
    ):
        raise LbError(
            "human-owned tasks accept only a status note (--kind 状态)", EXIT_REFUSED
        )
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

    semantic = field_value(note.removeprefix(ALARM_MARKER + " "))
    if semantic:
        field, annotation_value, _ = semantic
        if field in (Field.SOURCE, Field.ACCEPTANCE, Field.SKILLS, Field.STATUS):
            if not annotation_value.strip() or "<!--" in annotation_value:
                raise LbError(
                    "task detail must be nonempty visible single-line text", EXIT_USAGE
                )
        if field in (Field.SOURCE, Field.ACCEPTANCE) and task.state in ("x", "-"):
            raise LbError(
                "reopen the task before changing Source/Acceptance", EXIT_REFUSED
            )
        if field is Field.SKILLS:
            chain = skill_chain(annotation_value)
            if chain.diagnostics:
                raise LbError("invalid Skills chain", EXIT_USAGE)
            note = prefix(field, doc.locale) + "、".join(
                f"`/{name}`" for name in chain.names
            )
    if replace_line is not None:
        if (
            task.human
            or kind is None
            or not semantic
            or semantic[0] not in (Field.SOURCE, Field.ACCEPTANCE, Field.SKILLS, Field.STATUS)
        ):
            raise LbError(
                "replacement requires explicit Source/Acceptance/Skills/Status on an agent task",
                EXIT_REFUSED,
            )
        targets = [
            a
            for a in task.annotations
            if a.line == replace_line and a.kind is semantic[0]
        ]
        if len(targets) != 1:
            raise LbError(
                "replacement line must match the selected task and kind", EXIT_REFUSED
            )
        lines = list(doc.lines)
        old = lines[replace_line - 1]
        newline = "\r\n" if old.endswith("\r\n") else "\n" if old.endswith("\n") else ""
        suffix = " " + old[old.index("<!--") :].rstrip("\r\n") if "<!--" in old else ""
        lines[replace_line - 1] = f"    - {note}{suffix}{newline}"
        return "".join(lines), replace_line

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


def rewrite_task(
    doc: Document, task: Task, text: str, decision: str, assign_repo: str | None = None
) -> str:
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
    if assign_repo is not None:
        single_line(assign_repo, "repository")
        if task.repositories or updated.repositories != [assign_repo]:
            raise LbError(
                "--assign-repo requires an unassigned task and exactly the named repository in --text",
                EXIT_REFUSED,
            )
    if (
        updated.human
        or (assign_repo is None and updated.repositories != task.repositories)
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


def split_task(
    doc: Document, task: Task, texts: tuple[str, ...], decision: str
) -> str:
    """Replace one runnable package while keeping its identity and evidence."""
    single_line(decision, "decision")
    if task.human or task.state not in (" ", "/"):
        raise LbError("only unfinished agent tasks may be split", EXIT_REFUSED)
    if len(texts) < 2:
        raise LbError("split requires at least two --into values", EXIT_USAGE)
    for text in texts:
        single_line(text, "replacement task")
        if text.startswith(("- [", "* [", "+ [")):
            raise LbError("--into is task text only, without a checkbox", EXIT_USAGE)
    existing = {t.text for s in doc.stages if s.title == task.stage for t in s.tasks}
    if len(set(texts)) != len(texts) or existing.intersection(texts):
        raise LbError("replacement task text must be new and unique", EXIT_REFUSED)

    changed = doc.text[: task.state_at] + "-" + doc.text[task.state_at + 1 :]
    retired = parse_text(changed.encode("utf-8"), doc.path, doc.root)
    original = find_task(retired, task.stage, task.text)
    changed = resolve_task(
        retired,
        original,
        "not-applicable",
        decision,
        "Original package replaced by: " + json.dumps(texts, ensure_ascii=False),
    )
    retired = parse_text(changed.encode("utf-8"), doc.path, doc.root)
    original = find_task(retired, task.stage, task.text)
    last = task_content_end(retired, original)
    at = retired.offsets[last] + len(retired.lines[last])
    newline = "\r\n" if b"\r\n" in doc.data else "\n"
    source = prefix(Field.SOURCE, doc.locale) + (
        f"Split from original task {task.identity}; verify acceptance separately."
    )
    additions = "".join(
        f"- [ ] {text}{newline}    - {source}{newline}" for text in texts
    )
    changed = retired.text[:at] + additions + retired.text[at:]
    candidate = parse_text(changed.encode("utf-8"), doc.path, doc.root)
    replacements = [find_task(candidate, task.stage, text) for text in texts]
    if any(t.human or t.preflight_blocker for t in replacements):
        raise LbError("split cannot create human tasks or preflight gates", EXIT_REFUSED)
    if task.repositories:
        original_repositories = set(task.repositories)
        replacement_repositories = {r for t in replacements for r in t.repositories}
        if (
            any(not t.repositories for t in replacements)
            or replacement_repositories != original_repositories
        ):
            raise LbError(
                "split must preserve the original repository coverage without transfer",
                EXIT_REFUSED,
            )
    elif any(len(t.repositories) > 1 for t in replacements):
        raise LbError(
            "each replacement of an unassigned task may name at most one repository",
            EXIT_REFUSED,
        )
    return changed


def add_link(doc: Document, stage_name: str, link: str) -> tuple[str, int]:
    """Append one Markdown link to a delivery stage's related-links block."""
    if "\n" in link or "\r" in link or not LINK_RE.fullmatch(link.strip()):
        raise LbError("--link must be one Markdown link: [label](target)", EXIT_USAGE)
    link = link.strip()
    stages = [s for s in doc.stages if s.title == stage_name and s.is_delivery]
    if len(stages) != 1:
        raise LbError("delivery stage does not match uniquely", EXIT_REFUSED)
    stage = stages[0]
    later = [s.line - 1 for s in doc.stages if s.line > stage.line]
    stop = min(later) if later else len(doc.lines)
    fields: dict[Field, list[int]] = {Field.LINKS: [], Field.TODO: []}
    for index, line in visible_lines(doc.lines):
        if line is not None and stage.line <= index < stop:
            value = field_value(line)
            if value and value[0] in fields and not line.startswith((" ", "\t", "-")):
                fields[value[0]].append(index)
    newline = "\r\n" if b"\r\n" in doc.data else "\n"
    item = f"- {link}"
    if len(fields[Field.LINKS]) > 1:
        raise LbError("stage has more than one related-links field", EXIT_REFUSED)
    if fields[Field.LINKS]:
        index = fields[Field.LINKS][0]
        last = index
        for cursor in range(index + 1, stop):
            text = doc.lines[cursor].strip()
            if not text and last == index:
                continue
            if not text.startswith("- "):
                break
            if text == item:
                raise LbError("link already listed in this stage", EXIT_REFUSED)
            last = cursor
        at = doc.offsets[last] + len(doc.lines[last])
        separator = "" if doc.text[:at].endswith(("\n", "\r")) else newline
        if last == index:
            insert = f"{separator}{newline}{item}{newline}"
        else:
            insert = f"{separator}{item}{newline}"
        return doc.text[:at] + insert + doc.text[at:], last + 2
    if len(fields[Field.TODO]) != 1:
        raise LbError(
            "stage needs one Todo field to place a new related-links field",
            EXIT_REFUSED,
        )
    index = fields[Field.TODO][0]
    at = doc.offsets[index]
    label = prefix(Field.LINKS, doc.locale).rstrip()
    insert = f"{label}{newline}{newline}{item}{newline}{newline}"
    return doc.text[:at] + insert + doc.text[at:], index + 3


def link_path(doc: Document, target: str) -> Path:
    parsed = urlparse(target)
    if parsed.scheme == "file":
        return Path(unquote(parsed.path))
    raw = unquote(target.split("#", 1)[0])
    if raw.startswith("~"):
        return Path(os.path.expanduser(raw))
    return doc.path.parent / raw


def rewrite_links(doc: Document, old: str, new: str) -> tuple[str, list[dict]]:
    """Replace a target prefix in visible links; every rewritten target must exist."""
    if not old or old == new:
        raise LbError("--from must be nonempty and differ from --to", EXIT_USAGE)
    lines = list(doc.lines)
    rewritten = []
    for index, visible in visible_lines(doc.lines):
        if visible is None:
            continue

        def swap(match: re.Match[str]) -> str:
            label, target = match.group(1), match.group(2)
            if not target.startswith(old):
                return match.group(0)
            changed = new + target[len(old) :]
            rewritten.append({"line": index + 1, "from": target, "to": changed})
            return f"[{label}]({changed})"

        head = LINK_RE.sub(swap, visible)
        lines[index] = head + doc.lines[index][len(visible) :]
    missing = [r for r in rewritten if not link_path(doc, r["to"]).exists()]
    if missing:
        listed = "; ".join(f"line {r['line']}: {r['to']}" for r in missing)
        raise LbError(f"rewritten link target missing: {listed}", EXIT_REFUSED)
    return "".join(lines), rewritten
