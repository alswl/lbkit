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
    from logbook_cli import unified
    from logbook_cli.repository import read_document

    path = safe_path(base, log)
    _, value = unified.locate(base, path)
    return read_document(base, path) if value else parse(path, base)


def writable(root: str, log: str, token: str) -> Document:
    doc = load(root, log)
    if not doc.markdown_authority:
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


def save(doc: Document, changed: str, dry_run: bool, *, dependency_graph=None, **details: object) -> Result:
    from logbook_cli.state import encode, path_for, section, token

    if doc.markdown_authority:
        from logbook_cli.repository import edit_document

        for key, archived in doc.metadata.get("task-archive", {}).items():
            if "content" in archived:
                nl = "\r\n" if b"\r\n" in doc.data else "\n"
                fence = "`" * max(
                    3,
                    max(
                        (
                            len(m[0]) + 1
                            for m in __import__("re").finditer(
                                r"`{3,}", archived["content"]
                            )
                        ),
                        default=3,
                    ),
                )
                changed += (
                    nl
                    + "### Archived Task "
                    + key
                    + nl
                    + nl
                    + archived.get("basis", "")
                    + nl
                    + fence
                    + "markdown"
                    + nl
                    + archived["content"].rstrip()
                    + nl
                    + fence
                    + nl
                )
        require_valid_candidate(doc, changed)
        return Result({
            **edit_document(doc, changed, dry_run, dependency_graph=dependency_graph),
            **details,
        })
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
