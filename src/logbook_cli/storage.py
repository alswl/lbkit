"""Guarded filesystem writes with compare-and-swap and atomic replacement."""

import os
import tempfile
from pathlib import Path

from logbook_cli.document import EXIT_REFUSED, Document, LbError


def _sync_directory(path: Path) -> None:
    directory = os.open(path, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def create_bytes(path: Path, content: bytes, dry_run: bool) -> None:
    """Publish a complete new file without ever replacing an existing entry."""
    if path.exists() or path.is_symlink():
        raise LbError("create-only output already exists", EXIT_REFUSED)
    if dry_run:
        return
    fd, temporary = tempfile.mkstemp(prefix=".lb-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
            _sync_directory(path.parent)
        except FileExistsError as exc:
            raise LbError(
                "create-only output appeared concurrently", EXIT_REFUSED
            ) from exc
    finally:
        os.unlink(temporary)


def _replace(path: Path, data: bytes, expected: bytes | None) -> None:
    fd, temporary = tempfile.mkstemp(prefix=".lb-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            os.chmod(temporary, path.stat().st_mode)
        if (
            path.is_symlink()
            or (path.read_bytes() if path.exists() else None) != expected
        ):
            raise LbError(
                "file changed during write preparation: " + str(path), EXIT_REFUSED
            )
        if expected is None:
            # Create-only: never clobber a file that appeared after the check.
            try:
                os.link(temporary, path)
            except FileExistsError as exc:
                raise LbError(
                    "file appeared during write preparation: " + str(path),
                    EXIT_REFUSED,
                ) from exc
        else:
            os.replace(temporary, path)
        _sync_directory(path.parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def write_bytes(
    doc: Document, changed: bytes, dry_run: bool, *, create: bool = False
) -> None:
    """Serialize cooperating writers and journal recoverable two-file updates."""
    import base64
    import fcntl
    import json

    from logbook_cli.state import (
        encode,
        encode_file,
        journal_for,
        path_for,
        read_file,
        section,
    )

    if dry_run:
        return
    state = path_for(doc.path, doc.root)
    journal = journal_for(doc.path, doc.root)
    key = section(doc.path, doc.root)
    directory = os.open(doc.root, os.O_RDONLY)
    try:
        try:
            fcntl.flock(directory, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise LbError("another document writer is active", EXIT_REFUSED) from exc
        if journal.exists() or journal.is_symlink():
            raise LbError(
                "unfinished metadata transaction; use log recover", EXIT_REFUSED
            )
        if doc.path.is_symlink():
            raise LbError("document cannot be a symlink", EXIT_REFUSED)
        before = None if create else doc.data

        def stale(path):
            return LbError(
                "file changed since context; reread before writing: " + str(path),
                EXIT_REFUSED,
            )

        def verify():
            for path, expected in [(doc.path, before), *doc.dependencies]:
                if (
                    path.is_symlink()
                    or (path.read_bytes() if path.exists() else None) != expected
                ):
                    raise stale(path)
            # Other documents of the same mind may change their own sections.
            for path, expected in [(doc.path, doc.state_data), *doc.state_dependencies]:
                _, documents = read_file(path_for(path, doc.root))
                if encode(documents.get(section(path, doc.root), {})) != expected:
                    raise stale(path_for(path, doc.root))
            return read_file(state)

        state_before, documents = verify()
        state_after = state_before
        if encode(doc.metadata) != doc.state_data:
            documents = {k: v for k, v in documents.items() if k != key}
            if doc.metadata:
                documents[key] = doc.metadata
            state_after = encode_file(documents)
        changes = [
            (p, old, new)
            for p, old, new in [
                (doc.path, before, changed),
                (state, state_before, state_after),
            ]
            if old != new
        ]
        if not changes:
            return
        if state_after is not None:
            state.parent.mkdir(exist_ok=True)
        if len(changes) > 1:

            def encoded(data):
                return None if data is None else base64.b64encode(data).decode("ascii")

            payload = [
                {
                    "path": str(p.relative_to(doc.root)),
                    "before": encoded(old),
                    "after": encoded(new),
                }
                for p, old, new in changes
            ]
            create_bytes(journal, json.dumps(payload).encode(), False)
            # After this point an interrupted write is deliberately visible to readers.
            if verify()[0] != state_before:
                raise stale(state)
        for path, old, value in changes:
            if value is None:
                path.unlink()
                _sync_directory(path.parent)
            else:
                _replace(path, value, old)
        if len(changes) > 1:
            journal.unlink()
            _sync_directory(journal.parent)
    finally:
        os.close(directory)


def recover(root: Path, path: Path, expected: str | None, dry_run: bool) -> dict:
    """Roll forward only when every file still matches a recorded before/after image."""
    import base64
    import fcntl
    import hashlib
    import json

    from logbook_cli.state import journal_for, path_for

    directory = os.open(root, os.O_RDONLY)
    try:
        try:
            fcntl.flock(directory, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise LbError("another document writer is active", EXIT_REFUSED) from exc
        journal = journal_for(path, root)
        state = path_for(path, root)
        if journal.is_symlink() or not journal.is_file():
            raise LbError("no regular recovery journal", EXIT_REFUSED)
        data = journal.read_bytes()
        try:
            rows = json.loads(data)
            if not isinstance(rows, list) or not rows or len(rows) > 2:
                raise ValueError("invalid transaction entries")
            changes = []
            seen = set()
            for row in rows:
                if set(row) != {"path", "before", "after"}:
                    raise ValueError("invalid transaction target")
                relative = Path(row["path"])
                target = root / relative
                # Only this mind's state file and its own Markdown documents.
                if (
                    relative.is_absolute()
                    or ".." in relative.parts
                    or row["path"] in seen
                    or not (
                        target == state
                        or (target.suffix == ".md" and path_for(target, root) == state)
                    )
                ):
                    raise ValueError("invalid transaction target")
                seen.add(row["path"])
                if target.is_symlink():
                    raise ValueError("symlink transaction target")
                before, after = [
                    None if row[k] is None else base64.b64decode(row[k], validate=True)
                    for k in ("before", "after")
                ]
                current = target.read_bytes() if target.exists() else None
                if current not in (before, after):
                    raise ValueError(
                        "subsequent edit prevents recovery: " + row["path"]
                    )
                changes.append((target, current, after))
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            raise LbError(str(exc), EXIT_REFUSED) from exc
        token = hashlib.sha256(data).hexdigest()
        if not dry_run:
            if expected != token:
                raise LbError(
                    "use log recover --dry-run and its version_token", EXIT_REFUSED
                )
            for target, current, after in changes:
                if after is None:
                    target.unlink(missing_ok=True)
                else:
                    _replace(target, after, current)
            journal.unlink()
            _sync_directory(journal.parent)
        return {
            "version_token": token,
            "dry_run": dry_run,
            "recovered": not dry_run,
            "files": [str(p.relative_to(root)) for p, _, _ in changes],
        }
    finally:
        os.close(directory)
