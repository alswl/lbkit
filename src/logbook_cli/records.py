"""Reserved document records; all mutations use the existing CAS writer."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from logbook_cli.document import EXIT_REFUSED, EXIT_USAGE, Document, LbError
from logbook_cli.link_records import comment_open


def anchors(doc: Document, *, require_closed: bool = False) -> list[tuple[int, str]]:
    """Only task IDs are permitted as active reserved Markdown comments."""
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
            if line.strip().endswith("lb-run-events"):
                raise LbError(
                    "inline lb-run-events are unsupported; use document state",
                    EXIT_REFUSED,
                )
            fence = (match[1][0], len(match[1]))
            continue
        if line.lstrip().startswith("<!-- lb-"):
            anchor = re.fullmatch(
                r"\s*<!-- lb-task ([A-Za-z][A-Za-z0-9_-]{0,63}) -->\s*", line
            )
            if not anchor:
                raise LbError(
                    f"inline metadata is unsupported at line {index + 1}; use document state",
                    EXIT_REFUSED,
                )
            result.append((index, anchor[1]))
        else:
            comment = comment_open(line)
    if require_closed and (fence or comment):
        raise LbError(
            "unclosed fence/comment; cannot safely manage metadata", EXIT_REFUSED
        )
    return result


def read(
    doc: Document, kind: str, *, require_closed: bool = False
) -> list[tuple[int, dict]]:
    positions = anchors(doc, require_closed=require_closed)
    rows = doc.metadata.get(kind, {})
    for key, row in rows.items():
        identity = row.get("id") or row.get("record_id")
        if identity is not None and identity != key:
            raise LbError("state record key and identity disagree", EXIT_REFUSED)
    if kind == "task":
        ids = [identity for _, identity in positions]
        if len(ids) != len(set(ids)):
            raise LbError("duplicate task identity", EXIT_REFUSED)
        if set(ids) != set(rows):
            raise LbError(
                "missing or orphaned task state; reconcile task IDs and sidecar",
                EXIT_REFUSED,
            )
        return [(index, rows[identity]) for index, identity in positions]
    return [(-1, row) for row in rows.values()]


def append(doc: Document, kind: str, item: dict) -> str:
    return put(doc, kind, item)


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
    """Stage a record; the shared writer commits Markdown and state together."""
    anchors(doc, require_closed=True)
    if "document" not in doc.metadata:
        doc.metadata["document"] = {
            "identity": {"id": "identity", "uuid": uuid.uuid4().hex}
        }
    if kind == "run-event":
        import json

        key = json.dumps([item["run_id"], item["event_id"]])
    else:
        key = item.get("id") or item.get("record_id") or "singleton"
    doc.metadata.setdefault(kind, {})[key] = item
    return doc.text


def document_id(doc: Document) -> str | None:
    return doc.metadata.get("document", {}).get("identity", {}).get("uuid")
