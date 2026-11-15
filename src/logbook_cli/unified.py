"""Single-run storage: rebuildable document projections and independent facts."""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from contextlib import contextmanager
from pathlib import Path

from logbook_cli import state
from logbook_cli.document import EXIT_REFUSED, LbError

FORMAT = "task-document-projection"


def encode(value):
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode()


def digest(value):
    return hashlib.sha256(encode(value)).hexdigest()


def read(path):
    if path.is_symlink():
        raise LbError("unsafe unified state symlink", EXIT_REFUSED)
    try:
        value = json.loads(path.read_bytes(), object_pairs_hook=state.unique_object)
        if (
            not isinstance(value, dict)
            or set(value)
            != {"format", "identity", "documents", "execution", "monitoring"}
            or value["format"] != FORMAT
        ):
            raise ValueError("unsupported state format")
        identity = value["identity"]
        if (
            set(identity) != {"run_id", "log_path", "document_paths"}
            or not isinstance(identity["run_id"], str)
            or not isinstance(identity["document_paths"], list)
            or identity["log_path"] not in identity["document_paths"]
        ):
            raise ValueError("invalid identity")
        if any(
            not isinstance(v, str) or Path(v).is_absolute() or ".." in Path(v).parts
            for v in identity["document_paths"]
        ):
            raise ValueError("unsafe document association")
        if not isinstance(value["documents"], dict) or set(value["documents"]) - set(
            identity["document_paths"]
        ):
            raise ValueError("invalid documents")
        ex = value["execution"]
        if (
            not isinstance(ex, dict)
            or not isinstance(ex.get("tasks"), dict)
            or not isinstance(ex.get("operations"), dict)
            or not isinstance(ex.get("facts"), list)
        ):
            raise ValueError("invalid execution")
        if not re.fullmatch(r"[0-9a-f]{32}", identity["run_id"]):
            raise ValueError("invalid run ID")
        required_runtime = {
            "assignee",
            "assignment_revision",
            "assignment_history",
            "current_binding_id",
            "execution_bindings",
            "result_sources",
        }
        for key, runtime in ex["tasks"].items():
            if not isinstance(runtime, dict) or set(runtime) != required_runtime:
                raise ValueError("invalid Task runtime shape: " + key)
            if (
                not isinstance(runtime["assignment_revision"], int)
                or runtime["assignment_revision"] < 0
                or not isinstance(runtime["assignment_history"], list)
                or not isinstance(runtime["execution_bindings"], dict)
                or not isinstance(runtime["result_sources"], dict)
            ):
                raise ValueError("invalid Task runtime collections")
            if (
                runtime["current_binding_id"] is not None
                and runtime["current_binding_id"] not in runtime["execution_bindings"]
            ):
                raise ValueError("unknown current binding")
            owner = runtime["assignee"]
            if owner is not None and (
                not isinstance(owner, dict)
                or set(owner) != {"kind", "subject_id"}
                or owner["kind"] not in {"human", "agent"}
                or not isinstance(owner["subject_id"], str)
                or not owner["subject_id"].strip()
            ):
                raise ValueError("invalid Task assignee")
        for key, operation in ex["operations"].items():
            if (
                not isinstance(operation, dict)
                or operation.get("id") != key
                or operation.get("outcome")
                not in {"unknown", "submitted", "not_submitted"}
                or not isinstance(operation.get("request"), dict)
            ):
                raise ValueError("invalid send operation")
        if value["monitoring"] is not None and not isinstance(
            value["monitoring"], dict
        ):
            raise ValueError("invalid monitoring")
        return value
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise LbError(
            f"invalid unified state {path.name}: {exc}", EXIT_REFUSED
        ) from exc


def locate(root, log, *, required=False):
    directory = state.directory(log, root)
    relative = state.section(log, root)
    matches = []
    for path in sorted(directory.glob("*.json")):
        if path.is_symlink():
            raise LbError("unsafe state symlink", EXIT_REFUSED)
        # Old document sidecars never become new-run inputs.
        if path.name.endswith(".md.json"):
            continue
        try:
            raw = json.loads(path.read_bytes(), object_pairs_hook=state.unique_object)
        except (OSError, ValueError) as exc:
            raise LbError(f"invalid state {path.name}", EXIT_REFUSED) from exc
        if isinstance(raw, dict) and raw.get("format") == FORMAT:
            value = read(path)
            if relative in value["identity"]["document_paths"]:
                matches.append((path, value))
    if len(matches) > 1:
        raise LbError("multiple run identities bind this document", EXIT_REFUSED)
    if matches:
        if state.path_for(log, root).exists() or state.journal_for(log, root).exists():
            raise LbError("old document layout conflicts with unified run", EXIT_REFUSED)
        return matches[0]
    if required:
        raise LbError("initialization_required: run log init-state", EXIT_REFUSED)
    return None, None


@contextmanager
def writer(root, log, dry_run=False):
    if dry_run:
        yield
        return
    import fcntl

    directory = state.directory(log, root)
    directory.mkdir(exist_ok=True)
    fd = os.open(directory / ".lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise LbError(
                "writer_busy: another run writer is active", EXIT_REFUSED
            ) from exc
        yield
    finally:
        os.close(fd)


def publish(path, value):
    from logbook_cli.storage import replace_bytes_at

    before = path.read_bytes() if path.exists() else None
    data = encode(value)
    if before == data:
        return False
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        replace_bytes_at(fd, path.name, data, before)
    finally:
        os.close(fd)
    return True


def initialize(root, log, name, documents, dry_run=False):
    from logbook_cli.document import safe_path

    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", name):
        raise LbError("name must be a safe filename component", EXIT_REFUSED)
    base = state.project(log, root)
    paths = sorted(
        {
            state.section(log, root),
            *[str(safe_path(root, p).relative_to(base)) for p in documents],
        }
    )
    for relative in paths:
        target = safe_path(base, relative)
        if not target.is_file():
            raise LbError("associated document must exist", EXIT_REFUSED)
        if (
            state.path_for(target, root).exists()
            or state.journal_for(target, root).exists()
        ):
            raise LbError("old layout conflict; no migration", EXIT_REFUSED)
    target = state.directory(log, root) / (name + ".json")
    if (target.parent / "observations").exists() or (
        target.parent / "observations"
    ).is_symlink():
        raise LbError("old observations layout conflict; no migration", EXIT_REFUSED)
    with writer(root, log, dry_run):
        found, prior = locate(root, log)
        if found is not None and found != target:
            raise LbError("document already associated with another run", EXIT_REFUSED)
        if target.exists():
            prior = read(target)
            if prior["identity"]["document_paths"] != paths or prior["identity"][
                "log_path"
            ] != state.section(log, root):
                raise LbError("run identity conflict", EXIT_REFUSED)
            return {
                "changed": False,
                "path": str(target.relative_to(root)),
                "dry_run": dry_run,
            }
        for relative in paths:
            found, _ = locate(root, base / relative)
            if found:
                raise LbError(
                    "document already associated with another run", EXIT_REFUSED
                )
        value = {
            "format": FORMAT,
            "identity": {
                "run_id": uuid.uuid4().hex,
                "log_path": state.section(log, root),
                "document_paths": paths,
            },
            "documents": {},
            "execution": {"tasks": {}, "operations": {}, "facts": []},
            "monitoring": None,
        }
        if not dry_run:
            publish(target, value)
        return {
            "changed": True,
            "path": str(target.relative_to(root)),
            "dry_run": dry_run,
            "state": value,
        }


def section_token(value, section):
    return digest({"identity": value["identity"], section: value[section]})
