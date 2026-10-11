"""Guarded filesystem writes with compare-and-swap and atomic replacement."""

import os
import tempfile
from pathlib import Path

from logbook_cli.document import EXIT_REFUSED, Document, LbError, safe_path


def write_bytes(doc: Document, changed: bytes, dry_run: bool) -> None:
    if dry_run:
        return

    def current_path() -> Path:
        return safe_path(doc.root, str(doc.path))

    if current_path().read_bytes() != doc.data:
        raise LbError(
            "file changed since it was read; reread context before writing",
            EXIT_REFUSED,
        )
    fd, temporary = tempfile.mkstemp(prefix=".lb-", dir=doc.path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(changed)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, doc.path.stat().st_mode)
        # Recheck immediately before replace: fsync and metadata work can be
        # slow enough for another editor to change or replace the source.
        if current_path().read_bytes() != doc.data:
            raise LbError(
                "file changed during write preparation; reread context before writing",
                EXIT_REFUSED,
            )
        os.replace(temporary, doc.path)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise
