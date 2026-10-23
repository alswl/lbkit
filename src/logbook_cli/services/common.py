"""Common read and write boundaries for logbook use cases."""

import difflib
from dataclasses import dataclass

from logbook_cli.document import (
    Document,
    parse,
    require_preflight_clear,
    require_token,
    root_path,
    safe_path,
)
from logbook_cli.edit import require_valid_candidate
from logbook_cli.storage import write_bytes


@dataclass
class Result:
    value: object
    code: int = 0
    text: str | None = None


def load(root: str, log: str) -> Document:
    base = root_path(root)
    return parse(safe_path(base, log), base)


def writable(root: str, log: str, token: str) -> Document:
    doc = load(root, log)
    require_token(doc, token)
    require_preflight_clear(doc)
    from logbook_cli.document import EXIT_REFUSED, LbError
    from logbook_cli.lifecycle import get

    if get(doc)["value"] in {"paused", "completed", "terminated"}:
        raise LbError(
            "lifecycle stops ordinary writes; reconcile/reopen via state-set",
            EXIT_REFUSED,
        )
    return doc


def save(doc: Document, changed: str, dry_run: bool, **details: object) -> Result:
    from logbook_cli.state import encode, path_for, section, token

    require_valid_candidate(doc, changed)
    write_bytes(doc, changed.encode("utf-8"), dry_run)
    path = str(doc.path.relative_to(doc.root))
    value = {
        "path": path,
        "dry_run": dry_run,
        "issues_introduced": [],
        "version_token": doc.token
        if dry_run
        else token(changed.encode("utf-8"), encode(doc.metadata)),
        **details,
    }
    diff = None
    if dry_run:
        diff = "".join(
            difflib.unified_diff(
                doc.text.splitlines(keepends=True),
                changed.splitlines(keepends=True),
                fromfile=path,
                tofile=path,
            )
        )
        state_label = "{}#{}".format(
            path_for(doc.path, doc.root).relative_to(doc.root),
            section(doc.path, doc.root),
        )
        state_diff = "".join(
            difflib.unified_diff(
                (doc.state_data or b"").decode().splitlines(keepends=True),
                (encode(doc.metadata) or b"").decode().splitlines(keepends=True),
                fromfile=state_label,
                tofile=state_label,
            )
        )
        diff += state_diff
        value["diff"] = diff
    return Result(value, text=diff)
