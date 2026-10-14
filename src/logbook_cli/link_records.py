"""Offline observations bound to one visible link and current task conditions."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import TYPE_CHECKING

from logbook_cli.format import field_value, split_marker
from logbook_cli.models import Field

if TYPE_CHECKING:
    from logbook_cli.document import Document

MARKER = "<!-- lb-link-verification "
OUTCOMES = {"verified", "unavailable", "revoked"}


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() is None:
        raise ValueError("observation time requires a timezone")
    return parsed


def task_binding(doc: Document, stage: str, task: str) -> str:
    matches = [
        t for s in doc.stages if s.title == stage for t in s.tasks if t.text == task
    ]
    if len(matches) != 1:
        raise ValueError("missing or ambiguous bound task")
    item = matches[0]
    return digest(
        [
            stage,
            task,
            [
                [a.kind.value, a.value]
                for a in item.annotations
                if a.kind in (Field.SOURCE, Field.ACCEPTANCE, Field.ARTIFACT)
            ],
        ]
    )


def occurrence(doc: Document, link: dict) -> dict:
    from logbook_cli.document import visible_lines

    headings: dict[int, str] = {}
    visible = dict(visible_lines(doc.lines))
    for index, line in visible.items():
        if index >= link["line"]:
            break
        if line is None:
            continue
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if match:
            depth = len(match[1])
            headings = {k: v for k, v in headings.items() if k < depth}
            headings[depth] = split_marker(match[2])[0] if depth == 2 else match[2]
    owner = None
    for stage in doc.stages:
        for task in stage.tasks:
            if task.line == link["line"] or any(
                a.line == link["line"] for a in task.annotations
            ):
                owner = (stage.title, task.text)
                break
            if task.line < link["line"]:
                block = doc.lines[task.line : link["line"]]
                if block and all(
                    not body_line.strip() or body_line.startswith((" ", "\t"))
                    for body_line in block
                ):
                    owner = (stage.title, task.text)
    line = visible.get(link["line"] - 1) or ""
    line = re.sub(r"^([-*+] )\[[ /xX-]\] ", r"\1[] ", line.rstrip("\r\n"))
    raw_field = field_value(re.sub(r"^\s*[-*+]\s+", "", line))
    return {
        "anchor": digest(
            [
                list(headings.items()),
                owner,
                raw_field[0].value if raw_field else None,
                line,
                link["label"],
                link["target"],
            ]
        ),
        "task": {"stage": owner[0], "text": owner[1]} if owner else None,
    }


def comment_open(line: str, opened: bool = False) -> bool:
    position = 0
    while True:
        marker = "-->" if opened else "<!--"
        found = line.find(marker, position)
        if found == -1:
            return opened
        opened = not opened
        position = found + len(marker)


def comment_records(doc: Document) -> tuple[list[dict], list[dict], bool]:
    """Decode reserved whole-line comments only outside other comments/fences."""
    from logbook_cli.document import FENCE_RE

    records, errors = [], []
    fence: tuple[str, int] | None = None
    comment = False
    for index, line in enumerate(doc.lines):
        if fence:
            if re.match(
                rf"^[ \t]*{re.escape(fence[0])}{{{fence[1]},}}[ \t]*(?:\r?\n)?$", line
            ):
                fence = None
            continue
        if comment:
            comment = comment_open(line, True)
            continue
        start = FENCE_RE.match(line)
        if start:
            fence = (start[1], len(start[0].lstrip()))
            continue
        if line.startswith(MARKER):
            try:
                if not line.rstrip().endswith(" -->"):
                    raise ValueError("unterminated observation")
                payload = line.rstrip()[len(MARKER) : -4]
                if "<" in payload or ">" in payload:
                    raise ValueError("observation HTML delimiters must be escaped")
                record = json.loads(payload)
                required = {
                    "record_id",
                    "target",
                    "label",
                    "anchor",
                    "binding",
                    "bound_task",
                    "observed_at",
                    "observer",
                    "basis",
                    "outcome",
                    "result_identity",
                }
                if not isinstance(record, dict) or set(record) != required:
                    raise ValueError("invalid observation fields")
                if record["outcome"] not in OUTCOMES:
                    raise ValueError("invalid observation outcome")
                if any(
                    not isinstance(record[k], str) or not record[k].strip()
                    for k in (
                        "target",
                        "label",
                        "anchor",
                        "observed_at",
                        "observer",
                        "basis",
                    )
                ):
                    raise ValueError("invalid observation value")
                timestamp(record["observed_at"])
                if record["bound_task"] is not None and (
                    not isinstance(record["bound_task"], dict)
                    or set(record["bound_task"]) != {"stage", "text"}
                    or not all(
                        isinstance(v, str) and v for v in record["bound_task"].values()
                    )
                ):
                    raise ValueError("invalid observation binding")
                if record["binding"] is not None and not isinstance(
                    record["binding"], str
                ):
                    raise ValueError("invalid binding digest")
                if record["result_identity"] is not None and not isinstance(
                    record["result_identity"], str
                ):
                    raise ValueError("invalid result identity")
                if record["record_id"] != digest(
                    {k: v for k, v in record.items() if k != "record_id"}
                ):
                    raise ValueError("observation digest mismatch")
                records.append({**record, "metadata_line": index + 1})
            except (ValueError, TypeError, KeyError) as exc:
                errors.append({"line": index + 1, "reason": str(exc)})
                comment = comment_open(line)
            continue
        comment = comment_open(line)
    return records, errors, not (fence or comment)


def observations(doc: Document, links: list[dict]) -> tuple[list[dict], list[dict]]:
    records, errors, _ = comment_records(doc)
    located = [(link, occurrence(doc, link)) for link in links]
    result = []
    for record in records:
        matches = [
            link
            for link, item in located
            if item["anchor"] == record["anchor"]
            and link["target"] == record["target"]
            and link["label"] == record["label"]
        ]
        reason = None
        if len(matches) != 1:
            reason = "occurrence missing or ambiguous"
        elif record["bound_task"]:
            try:
                expected = task_binding(
                    doc, record["bound_task"]["stage"], record["bound_task"]["text"]
                )
                if record["binding"] != expected:
                    reason = "task inputs or result changed"
            except ValueError:
                reason = "bound task missing or ambiguous"
        result.append(
            {
                **record,
                "applicable": reason is None,
                "invalidation_reason": reason,
                "line": matches[0]["line"] if len(matches) == 1 else None,
            }
        )
    return result, errors


def verified_lines(doc: Document, links: list[dict]) -> set[tuple[int, str, str]]:
    records, _ = observations(doc, links)
    grouped: dict[tuple[int, str, str], list[dict]] = {}
    for record in records:
        if record["applicable"]:
            key = (record["line"], record["label"], record["target"])
            grouped.setdefault(key, []).append(record)
    verified = set()
    for key, values in grouped.items():
        latest_time = max(timestamp(r["observed_at"]) for r in values)
        latest = [r for r in values if timestamp(r["observed_at"]) == latest_time]
        if (
            all(r["outcome"] == "verified" for r in latest)
            and len({r["result_identity"] for r in latest}) <= 1
        ):
            verified.add(key)
    return verified


def encode(record: dict) -> str:
    value = (
        json.dumps(record, sort_keys=True, ensure_ascii=False)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )
    return MARKER + value + " -->"
