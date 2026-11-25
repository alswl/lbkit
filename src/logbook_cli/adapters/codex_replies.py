"""Read a local, owned Codex session's response to an exact preparation prompt."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from logbook_cli import state
from logbook_cli.document import EXIT_REFUSED, LbError


@dataclass(frozen=True)
class Reply:
    status: str
    observed_at: str
    digest: str
    evidence: str


def _text(payload, kind):
    parts = payload.get("content", ())
    if not isinstance(parts, list) or any(not isinstance(part, dict) for part in parts):
        return ""
    return "".join(
        part["text"]
        for part in parts
        if part.get("type") == kind and isinstance(part.get("text"), str)
    )


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _time(item):
    value = item.get("timestamp")
    try:
        moment = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    return moment if moment.utcoffset() is not None else None


def read_reply(
    session_id: str,
    directory: Path,
    request_id: str,
    prompt_digest: str,
    not_before: datetime,
    *,
    journal_root: Path | None = None,
) -> Reply | None:
    try:
        if str(uuid.UUID(session_id)) != session_id:
            raise ValueError("noncanonical ID")
    except ValueError as exc:
        raise LbError(
            "native Codex session identity unavailable", EXIT_REFUSED
        ) from exc
    root = (
        journal_root
        if journal_root is not None
        else Path.home() / ".codex" / "sessions"
    )
    matches = list(root.glob(f"*/*/*/*-{session_id}.jsonl"))
    if len(matches) != 1 or not matches[0].resolve().is_relative_to(root.resolve()):
        raise LbError(
            "a unique native Codex session journal is unavailable", EXIT_REFUSED
        )

    fd = os.open(matches[0], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as handle:
        meta = os.fstat(handle.fileno())
        if (
            not stat.S_ISREG(meta.st_mode)
            or meta.st_uid != os.getuid()
            or meta.st_mode & 0o022
        ):
            raise LbError("unsafe native Codex journal", EXIT_REFUSED)
        verified = False
        awaiting = False
        for raw in handle:
            if not raw.endswith(b"\n"):
                break  # A writer may still be appending its last record.
            item = json.loads(raw)
            if not isinstance(item, dict) or not isinstance(item.get("payload"), dict):
                continue
            payload = item["payload"]
            if item.get("type") == "session_meta":
                cwd = payload.get("cwd")
                if (
                    payload.get("id") != session_id
                    or not isinstance(cwd, str)
                    or Path(cwd).resolve() != directory.resolve()
                ):
                    raise LbError(
                        "native Codex session or work directory changed", EXIT_REFUSED
                    )
                verified = True
                continue
            if (
                not verified
                or item.get("type") != "response_item"
                or payload.get("type") != "message"
            ):
                continue
            when = _time(item)
            if when is None or when < not_before:
                continue
            if payload.get("role") == "user":
                awaiting = _digest(_text(payload, "input_text")) == prompt_digest
            elif (
                awaiting
                and payload.get("role") == "assistant"
                and payload.get("phase") == "final_answer"
                and payload.get("status") == "completed"
            ):
                return _result(_text(payload, "output_text"), request_id, when)
    if not verified:
        raise LbError("native Codex session metadata unavailable", EXIT_REFUSED)
    return None


def _result(message: str, request_id: str, when: datetime) -> Reply | None:
    try:
        value = json.loads(message, object_pairs_hook=state.unique_object)
    except (TypeError, ValueError, RecursionError):
        return None
    if (
        not isinstance(value, dict)
        or set(value) != {"self_check", "status", "evidence"}
        or value["self_check"] != request_id
        or value["status"] not in ("passed", "failed")
        or not isinstance(value["evidence"], str)
        or not value["evidence"].strip()
    ):
        return None
    return Reply(value["status"], when.isoformat(), _digest(message), value["evidence"].strip())
