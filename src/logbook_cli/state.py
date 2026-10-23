"""Document-owned state, kept outside human-readable Markdown.

Each mind keeps one `<project>/lb/<name>.md.json`. Same-named documents of the
mind (`docs/<name>.md`, `thinking/<name>.md`) own separate sections in it.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from logbook_cli.document import EXIT_REFUSED, LbError

FORMAT = "lb-document-state"


def project(path: Path, root: Path) -> Path:
    for parent in path.parents:
        if not parent.is_relative_to(root):
            break
        if (parent / "mind.yaml").is_file():
            return parent
    return root


def directory(path: Path, root: Path) -> Path:
    target = project(path, root) / "lb"
    if target.is_symlink() or (target.exists() and not target.is_dir()):
        raise LbError(
            "lb directory must be a real project-local directory", EXIT_REFUSED
        )
    return target


def path_for(path: Path, root: Path) -> Path:
    return directory(path, root) / (path.name + ".json")


def journal_for(path: Path, root: Path) -> Path:
    return directory(path, root) / (path.name + ".transaction")


def section(path: Path, root: Path) -> str:
    return str(path.relative_to(project(path, root)))


def token(data: bytes, state: bytes | None) -> str:
    # Length framing distinguishes absent state from an empty file.
    parts = [b"lb-document-state\0", str(len(data)).encode(), b":", data]
    parts += [b"absent" if state is None else b"present:" + state]
    return hashlib.sha256(b"".join(parts)).hexdigest()


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def validate(groups) -> None:
    if not isinstance(groups, dict) or any(
        not isinstance(rows, dict)
        or any(not isinstance(row, dict) for row in rows.values())
        for rows in groups.values()
    ):
        raise ValueError("records must map kinds and IDs to objects")
    identity = groups.get("document", {}).get("identity", {})
    if (
        set(identity) != {"id", "uuid"}
        or identity["id"] != "identity"
        or not isinstance(identity["uuid"], str)
        or len(identity["uuid"]) != 32
    ):
        raise ValueError("missing or invalid document identity")
    for kind, rows in groups.items():
        for key, row in rows.items():
            record_id = row.get("id") or row.get("record_id")
            if record_id is not None and record_id != key:
                raise ValueError("record key and identity disagree")
            if kind == "run-event" and key != json.dumps(
                [row.get("run_id"), row.get("event_id")]
            ):
                raise ValueError("run event key and identity disagree")


def read_file(target: Path) -> tuple[bytes | None, dict]:
    """Return raw bytes and the validated document sections of one state file."""
    if target.is_symlink():
        raise LbError("state file cannot be a symlink: " + str(target), EXIT_REFUSED)
    if not target.exists():
        return None, {}
    try:
        data = target.read_bytes()
        value = json.loads(data, object_pairs_hook=unique_object)
        if (
            not isinstance(value, dict)
            or set(value) != {"format", "documents"}
            or value["format"] != FORMAT
            or not isinstance(value["documents"], dict)
            or not value["documents"]
        ):
            raise ValueError("invalid state envelope")
        for groups in value["documents"].values():
            validate(groups)
        return data, value["documents"]
    except (OSError, ValueError, TypeError) as exc:
        raise LbError(f"invalid state file {target}: {exc}", EXIT_REFUSED) from exc


def load(path: Path, root: Path) -> tuple[bytes | None, dict]:
    """Return this document's section as canonical bytes plus its records."""
    journal = journal_for(path, root)
    if journal.exists() or journal.is_symlink():
        raise LbError(
            "unfinished metadata transaction; use log recover: " + str(path),
            EXIT_REFUSED,
        )
    _, documents = read_file(path_for(path, root))
    groups = documents.get(section(path, root), {})
    return encode(groups), groups


def encode(metadata: dict) -> bytes | None:
    """Canonical bytes of one document section; tokens and CAS bind to these."""
    if not metadata:
        return None
    return (
        json.dumps(metadata, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode()


def encode_file(documents: dict) -> bytes | None:
    if not documents:
        return None
    return (
        json.dumps(
            {"format": FORMAT, "documents": documents},
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n"
    ).encode()
