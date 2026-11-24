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
    if doc.markdown_authority:
        lines = doc.status_lines
        matches = {
            key
            for key, (glyph, zh, en) in VALUES.items()
            if any(
                re.match(
                    r"> (?:状态：|Status: )"
                    + re.escape(glyph)
                    + r"\s+(?:"
                    + re.escape(zh)
                    + "|"
                    + re.escape(en)
                    + r")(?:$| ·)",
                    row["raw"],
                )
                for row in lines
            )
        }
        if len(lines) > 1 or len(matches) > 1:
            raise LbError("ambiguous Markdown lifecycle", EXIT_REFUSED)
        return {"value": next(iter(matches), "unknown"), "managed": bool(matches)}
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
        stage_name = task.stage if task else ""
        blocked = bool(task and any("🚨" in a.value for a in task.annotations))
        if value == "active":
            for stage in doc.stages:
                if not stage.is_delivery:
                    continue
                active = next(
                    (t for t in stage.tasks if t.effective_state == "active"), None
                )
                has_blocked = any(t.effective_state == "blocked" for t in stage.tasks)
                if active or has_blocked:
                    task = active
                    stage_name = stage.title
                    blocked = has_blocked and active is None
                    break
        if stage_name:
            match = re.search(r"Stage\s+\d+[a-z]?", stage_name, re.I)
            if match:
                line += " · " + match[0]
        if doc.preflight:
            line += " · 🔮"
        elif task and task.human:
            line += " · " + ("Awaiting human" if english else "待人工")
        elif blocked:
            line += " · " + ("Blocked" if english else "受阻")
    from logbook_cli.execution import view as execution_view

    execution = execution_view(doc)
    current = next_task(doc)
    legacy = current and any(
        a.kind is Field.STATUS and "👨‍✈️" in a.value for a in current.annotations
    )
    if execution["reply_prefix"] or (execution["state"] is None and legacy):
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
            + r")(?: · Stage\s+\d+[a-z]?)?(?: · (?:待人工|受阻|🔮|Awaiting human|Blocked|状态不一致|Inconsistent))?(?: · 👨‍✈️ Captain takeover)?"
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
    if doc.markdown_authority:
        rows = summary_lines(doc)
        if len(rows) > 1:
            raise LbError("multiple status lines", EXIT_REFUSED)
        glyph, zh, en = VALUES[value]
        line = (
            "> Status: " + glyph + " " + en
            if doc.locale == "en"
            else "> 状态：" + glyph + " " + zh
        )
        nl = "\r\n" if b"\r\n" in doc.data else "\n"
        if rows:
            row = rows[0]
            changed = doc.text[: row["start"]] + line + nl + doc.text[row["end"] :]
        else:
            first = next(
                (i for i, line in enumerate(doc.lines) if line.startswith("# ")), None
            )
            if first is None:
                raise LbError("one H1 is required", EXIT_REFUSED)
            at = doc.offsets[first] + len(doc.lines[first])
            changed = doc.text[:at] + nl + line + nl + doc.text[at:]
        return save(doc, changed, dry_run, lifecycle=item)
    changed = records.put(doc, "lifecycle", item)
    candidate = parse_text(changed.encode(), doc.path, doc.root, source=doc)
    return save(doc, render(candidate), dry_run, lifecycle=item)
