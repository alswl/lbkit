"""Project-local execution ownership, independent of task completion."""

import hashlib
import json
import os
import re
from contextlib import contextmanager
from pathlib import Path

from logbook_cli import state
from logbook_cli.document import EXIT_REFUSED, LbError, context_command, parse_text
from logbook_cli.models import Field
from logbook_cli.storage import create_bytes, write_bytes


def project(doc):
    return state.project(doc.path, doc.root)


def directory(doc):
    return state.directory(doc.path, doc.root)


def validate(value, path):
    from logbook_cli import execution_facts as facts

    facts.fields(value, "name log thinking advancement captain facts operations")
    for key in ("name", "log", "thinking", "advancement", "captain"):
        facts.text(value[key])
    if (
        value["name"] != path.stem
        or not isinstance(value["facts"], list)
        or not isinstance(value["operations"], list)
    ):
        facts.refuse("invalid execution identity or record collections")
    seen = set()
    prior = []
    for fact in value["facts"]:
        facts.validate_fact(fact, prior)
        if fact["id"] in seen:
            facts.refuse("duplicate fact ID")
        seen.add(fact["id"])
        prior.append(fact)
    seen = set()
    for op in value["operations"]:
        facts.fields(op, "id request outcome receipt provenance")
        facts.text(op["id"])
        if (
            op["id"] in seen
            or op["outcome"] not in ("unknown", "submitted", "not_submitted")
            or op["provenance"]
            not in ("adapter", "caller_reported_runtime_observation")
        ):
            facts.refuse("invalid transport operation record")
        seen.add(op["id"])
        request = op["request"]
        optional = " task_id" if isinstance(request, dict) and "task_id" in request else ""
        facts.fields(
            request,
            "dispatch_id recipient session_id binding_digest message_digest package_digest" + optional,
        )
        for v in op["request"].values():
            facts.text(v)
    return value


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def read(doc):
    path, data, value, _ = _read(doc)
    return path, data, value


def _read(doc):
    if doc.markdown_authority:
        from logbook_cli import unified

        path, envelope = unified.locate(doc.root, doc.path, required=True)
        ex = envelope["execution"]
        identity = envelope["identity"]
        value = {
            "name": path.stem,
            "log": identity["log_path"],
            "thinking": next(
                (p for p in identity["document_paths"] if p != identity["log_path"]),
                identity["log_path"],
            ),
            "advancement": ex.get("advancement", path.stem),
            "captain": ex.get("captain", "captain"),
            "facts": ex["facts"],
            "operations": list(ex["operations"].values()),
        }
        raw = unified.section_content(envelope, "execution")
        return path, raw, value, ex
    return (*find_legacy(doc.root, doc.path, strict=False), None)


def matches_binding(base, binding, document):
    if not state.is_filesystem_path(binding):
        return False
    candidate = Path(os.path.normpath(base / binding))
    if candidate == document:
        return True
    if candidate.is_relative_to(base):
        try:
            return candidate.resolve() == document
        except (OSError, RuntimeError):
            return False
    return False


def find_legacy(root, document, *, include_thinking=False, strict=True):
    """Find the legacy execution record by document binding, independent of name."""
    base = state.project(document, root)
    fields = ("log", "thinking") if include_thinking else ("log",)
    matches = []
    for path in sorted(state.directory(document, root).glob("*.json")):
        if path.name.endswith(".md.json"):
            continue
        try:
            data = state.read_regular(root, path)
            value = state.decode_json(data)
        except (ValueError, OSError) as exc:
            raise LbError(
                f"invalid or unsafe execution state: {path.name}", EXIT_REFUSED
            ) from exc
        if not isinstance(value, dict):
            continue
        if strict:
            if not any(matches_binding(base, value.get(key), document) for key in fields):
                continue
        elif value.get("log") != document.relative_to(base).as_posix():
            continue
        try:
            validate(value, path)
            for key in ("log", "thinking"):
                relative = Path(value[key])
                bound = base / relative
                if relative.is_absolute() or ".." in relative.parts:
                    raise LbError("invalid execution document binding", EXIT_REFUSED)
                if strict:
                    if (
                        value[key] != relative.as_posix()
                        or state.project(bound, root) != base
                        or value["thinking"] == value["log"]
                    ):
                        raise LbError("invalid execution document binding", EXIT_REFUSED)
                    with state.open_regular(root, bound):
                        pass
                elif not bound.is_file() or not bound.resolve().is_relative_to(base):
                    raise LbError(
                        "execution document binding is missing or outside project; reconcile binding",
                        EXIT_REFUSED,
                    )
        except (LbError, OSError, ValueError) as exc:
            detail = exc.message if isinstance(exc, LbError) else str(exc)
            raise LbError(
                f"invalid execution state {path.name}: {detail}", EXIT_REFUSED
            ) from exc
        matches.append((path, data, value))
    if len(matches) > 1:
        kind = "document" if include_thinking else "Logbook"
        raise LbError(f"multiple execution states bind this {kind}", EXIT_REFUSED)
    return matches[0] if matches else (None, b"", None)


def initial(doc, thinking, name=None, advancement=None, captain=None):
    """New empty record; name defaults to the Logbook stem, advancement to name."""
    base = project(doc)
    if thinking.path == doc.path or not thinking.path.is_relative_to(base):
        raise LbError(
            "Thinking must be a distinct document in the same project", EXIT_REFUSED
        )
    name = name or doc.path.stem
    return {
        "name": name,
        "thinking": str(thinking.path.relative_to(base)),
        "log": str(doc.path.relative_to(base)),
        "advancement": advancement or name,
        "captain": captain or "captain",
        "facts": [],
        "operations": [],
    }


def projection(value, runtime=None, *, task_id=None, dispatch_id=None):
    from logbook_cli.execution_facts import project

    result = project(
        value["facts"] if value else [], runtime, task_id=task_id, dispatch_id=dispatch_id
    )
    result["unresolved_operations"] = (
        [op["id"] for op in value["operations"] if op["outcome"] == "unknown"]
        if value
        else []
    )
    if result["unresolved_operations"]:
        release = result["release"]
        pending_task_handoff = (
            release and release["scope"] == "task"
            and result["reported_owner"] == value["captain"]
            and all(
                op["request"].get("release_id") == release["id"]
                for op in value["operations"] if op["outcome"] == "unknown"
            )
        )
        result.update(handoff_reported_complete=False, restricted=True)
        if not pending_task_handoff:
            result["reported_owner"] = "unknown"
    result["reply_prefix"] = (
        "👨‍✈️" if value and result["reported_owner"] == value["captain"] else ""
    )
    return result


def view(doc):
    from logbook_cli.document import summary_lines

    path, data, value, runtime = _read(doc)
    result = projection(value, runtime)
    markers = ["👨‍✈️" in row["raw"] for row in summary_lines(doc)]
    return {
        "path": str(path.relative_to(doc.root)) if path else None,
        "version_token": hashlib.sha256(data).hexdigest(),
        "state": value,
        "delegation_restricted": result["restricted"],
        "reply_prefix": result["reply_prefix"],
        "projection": result,
        "page_projection_matches": (
            len(markers) == 1 and markers[0] == bool(result["reply_prefix"])
        )
        if value
        else None,
        "fact_assurance": "caller-reported sources; not independently verified by CLI",
        "runtime_transfer_verified": False,
    }


def operation_task(operation):
    return operation.get("legacy_task_id", operation["request"].get("task_id"))


def require_delegation(doc, dispatch_id=None, owner=None, *, task_id=None):
    _, _, value = read(doc)
    if value is None:
        if any(
            a.kind is Field.STATUS and "👨‍✈️" in a.value
            for stage in doc.stages
            for task in stage.tasks
            for a in task.annotations
        ):
            raise LbError(
                "legacy Captain takeover marker requires execution JSON reconciliation before delegation",
                EXIT_REFUSED,
            )
        return
    result = projection(value, task_id=task_id, dispatch_id=dispatch_id)
    release = result["release"]
    if result["unresolved_operations"]:
        raise LbError(
            "transport outcome unknown; reconcile before further delegation",
            EXIT_REFUSED,
        )
    if not result["restricted"]:
        return
    if (
        release
        and release["recipient"] == owner
        and (
            release["scope"] == "task" and release["task_id"] == task_id
            or release["scope"] != "task" and release["dispatch_id"] == dispatch_id
        )
    ):
        return release
    raise LbError(
        "Captain takeover restricts delegation across tasks; keep independent review pending until recorded release applies",
        EXIT_REFUSED,
    )


def require_token(doc, path, data, token):
    if token != hashlib.sha256(data).hexdigest():
        target = (
            str(path.relative_to(doc.root)) if path else "uninitialized execution JSON"
        )
        raise LbError(
            f"execution version token differs for {target}; "
            f"reread `{context_command(doc, execution=True)}` and review changes before retrying. "
            "Extract version_token programmatically; the Logbook/Thinking token does not protect this JSON.",
            EXIT_REFUSED,
        )


def write(doc, name, value, token, dry_run):
    if doc.markdown_authority:
        from logbook_cli import unified

        path, raw, old = read(doc)
        require_token(doc, path, raw, token)
        target, envelope = unified.locate(doc.root, doc.path, required=True)
        if name != target.stem:
            raise LbError("execution name already bound", EXIT_REFUSED)
        prior = []
        from logbook_cli import execution_facts

        for fact in value["facts"]:
            execution_facts.validate_fact(fact, prior)
            prior.append(fact)
        ex = envelope["execution"]
        ex.update(
            facts=value["facts"],
            operations={op["id"]: op for op in value["operations"]},
        )
        for key in ("captain", "advancement"):
            if value.get(key) != old.get(key):
                ex[key] = value[key]
        changed = value != old
        if changed and not dry_run:
            unified.publish_run(doc.root, target, envelope, requires_dependencies=False)
        return {
            "path": str(target.relative_to(doc.root)),
            "state": value,
            "version_token": token
            if dry_run
            else unified.section_token(envelope, "execution"),
            "changed": changed,
            "dry_run": dry_run,
            "record_saved": not dry_run,
            "projection": projection(value, ex),
        }
    path, data, old = read(doc)
    require_token(doc, path, data, token)
    # `<name>.md.json` belongs to document state of the same mind.
    if (
        not re.fullmatch(r"[\w][\w.-]*", name)
        or name in {".", ".."}
        or name.endswith(".md")
    ):
        raise LbError(
            "execution name must be one stable filename component not ending in .md",
            EXIT_REFUSED,
        )
    target = directory(doc) / f"{name}.json"
    if path and path != target:
        raise LbError("execution name is already bound", EXIT_REFUSED)
    validate(value, target)
    changed = (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()
    if value == old:
        return view(doc) | {
            "dry_run": dry_run,
            "changed": False,
            "record_saved": not dry_run,
            "effect": "existing record; no runtime operation",
        }
    if path:
        write_bytes(parse_text(data, path, doc.root), changed, dry_run)
    else:
        if not dry_run:
            target.parent.mkdir(exist_ok=True)
        create_bytes(target, changed, dry_run)
    projected = projection(value)
    return {
        "path": str(target.relative_to(doc.root)),
        "state": value,
        "version_token": token if dry_run else hashlib.sha256(changed).hexdigest(),
        "dry_run": dry_run,
        "changed": True,
        "effect": "record only; no runtime operation",
        "record_saved": not dry_run,
        "delegation_restricted": projected["restricted"],
        "reply_prefix": projected["reply_prefix"],
        "projection": projected,
        "runtime_transfer_verified": False,
        "fact_assurance": "caller-reported sources; not independently verified by CLI",
    }


@contextmanager
def writer(doc, dry_run=False):
    """Serialize cooperating writers; never wait on another runtime operation."""
    if dry_run:
        yield
        return
    import fcntl

    base = directory(doc)
    base.mkdir(exist_ok=True)
    fd = os.open(base / ".lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise LbError(
                "execution writer busy; reread context and retry later", EXIT_REFUSED
            ) from exc
        from logbook_cli import unified

        if bool(unified.locate(doc.root, doc.path)[0]) != doc.markdown_authority:
            raise LbError("execution authority changed; reread context", EXIT_REFUSED)
        yield
    finally:
        os.close(fd)


def serialized(function):
    """Apply the same writer lock to dispatch/binding mutations and send intent."""
    from functools import wraps
    from inspect import signature

    parameters = signature(function)

    @wraps(function)
    def call(*args, **kwargs):
        from logbook_cli.services.common import load

        bound = parameters.bind(*args, **kwargs).arguments
        doc = load(bound["root"], bound["log"])
        with writer(doc, bound.get("dry_run", False)):
            return function(*args, **kwargs)

    return call
