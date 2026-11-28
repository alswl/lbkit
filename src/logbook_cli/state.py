"""Document-owned state, kept outside human-readable Markdown.

Each mind keeps one `<project>/lb/<name>.md.json`. Same-named documents of the
mind (`docs/<name>.md`, `thinking/<name>.md`) own separate sections in it.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
from contextlib import contextmanager
from pathlib import Path

from logbook_cli.document import EXIT_PATH, EXIT_REFUSED, LbError, path_error, safe_path

FORMAT = "lb-document-state"
MARKDOWN_SUFFIXES = (".md", ".markdown")


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
    return path.relative_to(project(path, root)).as_posix()


def project_key(
    path: Path,
    base: Path,
    field: str,
    value: str,
    *,
    root: Path | None = None,
    code: int = EXIT_PATH,
) -> str:
    if not path.is_relative_to(base) or project(path, base) != base:
        raise path_error(
            field, value, root or base, f"path belongs outside the Logbook project {base}",
            code=code,
        )
    return path.relative_to(base).as_posix()


def project_relative_path(base: Path, key: str, field: str) -> Path:
    if not is_filesystem_path(key):
        raise path_error(field, key, base, "expected a project-relative file key")
    relative = Path(key)
    if (
        relative.is_absolute()
        or relative == Path(".")
        or ".." in relative.parts
        or relative.as_posix() != key
    ):
        raise path_error(field, key, base, "expected a project-relative file key")
    return base / relative


def project_file(base: Path, key: str, field: str) -> Path:
    candidate = project_relative_path(base, key, field)
    project_key(candidate, base, field, key)
    path = safe_path(base, key, field=field)
    project_key(path, base, field, key)
    return path


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


def decode_json(data: bytes):
    try:
        return json.loads(data, object_pairs_hook=unique_object)
    except RecursionError as exc:
        raise ValueError("JSON nesting is too deep") from exc


def document_identity(groups) -> dict:
    document = groups.get("document") if isinstance(groups, dict) else None
    identity = document.get("identity") if isinstance(document, dict) else None
    return identity if isinstance(identity, dict) else {}


def validate_identity(groups) -> str:
    identity = document_identity(groups)
    if (
        set(identity) != {"id", "uuid"}
        or identity["id"] != "identity"
        or not isinstance(identity["uuid"], str)
        or len(identity["uuid"]) != 32
    ):
        raise ValueError("missing or invalid document identity")
    return identity["uuid"]


def validate(groups) -> None:
    if not isinstance(groups, dict) or any(
        not isinstance(rows, dict)
        or any(not isinstance(row, dict) for row in rows.values())
        for rows in groups.values()
    ):
        raise ValueError("records must map kinds and IDs to objects")
    validate_identity(groups)
    for kind, rows in groups.items():
        for key, row in rows.items():
            record_id = row.get("id") or row.get("record_id")
            if record_id is not None and record_id != key:
                raise ValueError("record key and identity disagree")
            if kind == "run-event" and key != json.dumps(
                [row.get("run_id"), row.get("event_id")]
            ):
                raise ValueError("run event key and identity disagree")


@contextmanager
def open_directory(root: Path, directory: Path):
    parts = directory.relative_to(root).parts
    if ".." in parts:
        raise OSError("invalid root-relative directory")
    fd = os.open(root, os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY)
    try:
        for part in parts:
            child = os.open(
                part, os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY, dir_fd=fd
            )
            os.close(fd)
            fd = child
        yield fd
    finally:
        os.close(fd)


def is_filesystem_path(value) -> bool:
    """Return whether a textual path can be passed to filesystem calls."""
    if not isinstance(value, str) or not value or "\0" in value:
        return False
    try:
        os.fsencode(value)
    except UnicodeEncodeError:
        return False
    return True


@contextmanager
def open_regular(root: Path, path: Path):
    """Open a regular file without following links or waiting on a FIFO."""
    if not path.is_relative_to(root) or path == root or path.name in {".", ".."}:
        raise OSError("invalid root-relative file path")
    with open_directory(root, path.parent) as fd:
        source = os.open(
            path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd
        )
        with os.fdopen(source, "rb") as handle:
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                raise OSError("expected a regular file")
            yield handle


def read_regular(root: Path, path: Path, limit: int | None = None) -> bytes:
    with open_regular(root, path) as handle:
        return handle.read() if limit is None else handle.read(limit + 1)


def read_envelope(target: Path, *, root: Path | None = None):
    """Read a state file without interpreting its individual records."""
    if target.is_symlink():
        raise LbError("state file cannot be a symlink: " + str(target), EXIT_REFUSED)
    if not target.exists():
        return None, None
    try:
        data = read_regular(target.parent if root is None else root, target)
        return data, decode_json(data)
    except (OSError, ValueError, TypeError) as exc:
        raise LbError(f"invalid state file {target}: {exc}", EXIT_REFUSED) from exc


def document_sections(value) -> dict:
    if (
        not isinstance(value, dict)
        or set(value) != {"format", "documents"}
        or value["format"] != FORMAT
        or not isinstance(value["documents"], dict)
        or not value["documents"]
    ):
        raise ValueError("invalid state envelope")
    return value["documents"]


def read_file(target: Path, *, root: Path | None = None) -> tuple[bytes | None, dict]:
    """Return raw bytes and the validated document sections of one state file."""
    data, value = read_envelope(target, root=root)
    if data is None:
        return None, {}
    try:
        sections = document_sections(value)
        for groups in sections.values():
            validate(groups)
        return data, sections
    except (ValueError, TypeError) as exc:
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
