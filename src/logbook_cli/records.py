"""Reserved document records; all mutations use the existing CAS writer."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from logbook_cli.document import EXIT_REFUSED, EXIT_USAGE, Document, LbError
from logbook_cli.link_records import comment_open


def read(
    doc: Document, kind: str, *, require_closed: bool = False
) -> list[tuple[int, dict]]:
    marker = f"<!-- lb-{kind} "
    result = []
    fence = None
    comment = False
    for index, line in enumerate(doc.lines):
        if fence:
            if re.fullmatch(rf"\s*{re.escape(fence[0])}{{{fence[1]},}}\s*", line):
                fence = None
            continue
        if comment:
            comment = comment_open(line, True)
            continue
        match = re.match(r"^\s*(`{3,}|~{3,})", line)
        if match:
            fence = (match[1][0], len(match[1]))
            continue
        record_line = line.lstrip() if kind == "task" else line
        if record_line.startswith(marker):
            try:
                if not record_line.rstrip().endswith(" -->"):
                    raise ValueError("unterminated record")
                payload = record_line.rstrip()[len(marker) : -4]
                if "<" in payload or ">" in payload:
                    raise ValueError("unescaped HTML delimiter")
                item = json.loads(payload)
                if not isinstance(item, dict):
                    raise ValueError("record must be an object")
            except (ValueError, TypeError) as exc:
                raise LbError(
                    f"invalid {kind} record at line {index + 1}: {exc}", EXIT_REFUSED
                ) from exc
            result.append((index, item))
        else:
            comment = comment_open(line)
    if require_closed and (fence or comment):
        raise LbError(
            "unclosed fence/comment; cannot safely manage metadata", EXIT_REFUSED
        )
    return result


def encode(kind: str, item: dict) -> str:
    payload = json.dumps(item, ensure_ascii=False, sort_keys=True)
    payload = payload.replace("<", "\\u003c").replace(">", "\\u003e")
    return f"<!-- lb-{kind} {payload} -->"


def append(doc: Document, kind: str, item: dict) -> str:
    read(doc, kind, require_closed=True)
    nl = "\r\n" if b"\r\n" in doc.data else "\n"
    return (
        doc.text
        + ("" if doc.text.endswith("\n") else nl)
        + nl
        + encode(kind, item)
        + nl
    )


def single_line(value: str, name: str) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or any(c in value for c in "\r\n")
    ):
        raise LbError(f"{name} must be a nonempty single line", EXIT_USAGE)
    return value


def observed(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.utcoffset() is None or parsed > datetime.now(timezone.utc):
            raise ValueError("time must be timezone-qualified and not in the future")
    except (ValueError, TypeError) as exc:
        raise LbError(str(exc), EXIT_USAGE) from exc
    return value


def put(doc: Document, kind: str, item: dict) -> str:
    """Replace one identified record or append it; callers own transition rules."""
    rows = read(doc, kind, require_closed=True)
    matches = [(index, row) for index, row in rows if row.get("id") == item["id"]]
    if len(matches) > 1:
        raise LbError(f"duplicate {kind} ID", EXIT_REFUSED)
    if not matches:
        return append(doc, kind, item)
    index, _ = matches[0]
    nl = "\r\n" if b"\r\n" in doc.data else "\n"
    return (
        doc.text[: doc.offsets[index]]
        + encode(kind, item)
        + nl
        + doc.text[doc.offsets[index] + len(doc.lines[index]) :]
    )
