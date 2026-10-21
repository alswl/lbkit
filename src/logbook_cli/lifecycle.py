"""Lifecycle facts and a compact CLI-owned page summary."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from logbook_cli import records
from logbook_cli.document import (
    EXIT_REFUSED,
    Document,
    LbError,
    next_task,
    parse_text,
    require_preflight_clear,
    require_token,
    summary_lines,
)
from logbook_cli.models import Field
from logbook_cli.services.common import Result, load, save
from logbook_cli.task_identity import acceptance_issues

VALUES = {
    "draft": ("📝", "草稿", "Draft"),
    "ready": ("🛫", "待执行", "Ready"),
    "active": ("🚧", "进行中", "Active"),
    "paused": ("⏸", "暂停", "Paused"),
    "completed": ("✅", "已完成", "Completed"),
    "terminated": ("⛔", "已终止", "Terminated"),
    "unknown": ("❔", "状态未核对", "Unknown"),
}
TRANSITIONS = {
    "unknown": set(VALUES) - {"unknown"},
    "draft": {"draft", "ready", "terminated"},
    "ready": {"ready", "draft", "active", "paused", "completed", "terminated"},
    "active": {"active", "paused", "completed", "terminated"},
    "paused": {"paused", "active", "terminated"},
    "completed": {"completed", "draft", "ready", "active"},
    "terminated": {"terminated", "draft", "ready"},
}


def get(doc: Document) -> dict:
    items = records.read(doc, "lifecycle")
    if len(items) > 1:
        raise LbError("duplicate lifecycle records", EXIT_REFUSED)
    if not items:
        return {"value": "unknown", "managed": False}
    item = items[0][1]
    if (
        set(item) != {"value", "basis", "at", "previous"}
        or not isinstance(item["value"], str)
        or item["value"] not in VALUES
        or item["value"] == "unknown"
    ):
        raise LbError("invalid lifecycle metadata", EXIT_REFUSED)
    records.single_line(item["basis"], "basis")
    records.observed(item["at"])
    return {**item, "managed": True}


def compact(doc: Document) -> str:
    item = get(doc)
    value = item["value"]
    tasks = [t for s in doc.stages if s.is_delivery for t in s.tasks]
    inconsistent = value == "completed" and (
        not tasks or any(not t.settled for t in tasks) or bool(acceptance_issues(doc))
    )
    emoji, zh, en = VALUES[value]
    english = doc.locale == "en"
    line = f"> {'Status: ' if english else '状态：'}{emoji} {en if english else zh}"
    if inconsistent:
        return line + (" · Inconsistent" if english else " · 状态不一致")
    if value in {"draft", "ready", "active", "unknown"}:
        task = next_task(doc)
        if task:
            match = re.search(r"Stage\s+\d+[a-z]?", task.stage, re.I)
            if match:
                line += " · " + match[0]
        if doc.preflight:
            line += " · 🔮"
        elif task and task.human:
            line += " · " + ("Awaiting human" if english else "待人工")
        elif task:
            # Only the current task's status/blocker annotation can qualify it.
            if any("🚨" in a.value for a in task.annotations):
                line += " · " + ("Blocked" if english else "受阻")
    current = next_task(doc)
    if current and any(a.kind is Field.STATUS and "👨‍✈️" in a.value for a in current.annotations):
        line += " · 👨‍✈️ Captain takeover"
    return line


def render(doc: Document) -> str:
    lines = summary_lines(doc)
    if len(lines) > 1:
        raise LbError("multiple page status lines; reconcile before sync", EXIT_REFUSED)
    line = compact(doc)
    nl = "\r\n" if b"\r\n" in doc.data else "\n"
    if lines:
        record = lines[0]
        # Preserve legacy human commentary; migration must be an explicit edit.
        if not get(doc)["managed"] and not record["raw"].startswith(
            ("> 状态：❔ ", "> Status: ❔ ")
        ):
            return doc.text
        raw = record["raw"]
        labels = [f"{v[0]} {v[i]}" for v in VALUES.values() for i in (1, 2)]
        pattern = (
            r"> (?:状态：|Status: )(?:"
            + "|".join(re.escape(v) for v in labels)
            + r")(?: · Stage\s+\d+[a-z]?)?(?: · (?:待人工|受阻|🔮|Awaiting human|Blocked|状态不一致|Inconsistent))?"
        )
        if not re.fullmatch(pattern, raw):
            raise LbError(
                "human status/commentary requires explicit migration", EXIT_REFUSED
            )
        start, end = record["start"], record["end"]
        return doc.text[:start] + line + nl + doc.text[end:]
    from logbook_cli.document import visible_lines

    h1 = [
        i for i, text in visible_lines(doc.lines) if text and re.match(r"^#\s+", text)
    ]
    if len(h1) != 1:
        raise LbError("one H1 is required for a generated status", EXIT_REFUSED)
    at = doc.offsets[h1[0]] + len(doc.lines[h1[0]])
    prefix = "" if doc.text[:at].endswith("\n") else nl
    return doc.text[:at] + prefix + nl + line + nl + doc.text[at:]


def set_state(
    root: str, log: str, value: str, basis: str, token: str, dry_run: bool
) -> Result:
    doc = load(root, log)
    require_token(doc, token)
    records.read(doc, "lifecycle", require_closed=True)
    old = get(doc)
    records.single_line(basis, "basis")
    if value not in TRANSITIONS[old["value"]]:
        raise LbError("invalid lifecycle transition", EXIT_REFUSED)
    if value not in {"paused", "terminated"}:
        require_preflight_clear(doc)
    tasks = [t for s in doc.stages if s.is_delivery for t in s.tasks]
    if value == "completed" and (
        not tasks or any(not t.settled for t in tasks) or acceptance_issues(doc)
    ):
        raise LbError("completion requires a nonempty settled checklist", EXIT_REFUSED)
    item = {
        "value": value,
        "basis": basis,
        "at": datetime.now(timezone.utc).isoformat(),
        "previous": old["value"],
    }
    existing = records.read(doc, "lifecycle")
    if existing:
        index = existing[0][0]
        nl = "\r\n" if b"\r\n" in doc.data else "\n"
        changed = (
            doc.text[: doc.offsets[index]]
            + records.encode("lifecycle", item)
            + nl
            + doc.text[doc.offsets[index] + len(doc.lines[index]) :]
        )
    else:
        changed = records.append(doc, "lifecycle", item)
    candidate = parse_text(changed.encode(), doc.path, doc.root)
    return save(doc, render(candidate), dry_run, lifecycle=item)
