"""Read and update the bounded readiness evidence section in Thinking."""

import json
import re

from logbook_cli import state, unified
from logbook_cli.document import (
    EXIT_REFUSED,
    LbError,
    path_error,
    safe_path,
    visible_lines,
)
from logbook_cli.state import unique_object

HEADING = "## 路线确认与预检"
HEADINGS = re.compile(r"(?m)^## 路线确认与预检[ \t]*\r?$")
NEXT_HEADING = re.compile(r"(?m)^#{1,2} ")
FIELDS = {"run_ref", "confirmations", "observations", "grants"}


def _validate_observation(row):
    if "action" not in row:
        return
    task_id = row.get("task_id")
    if (
        row["action"] not in ("dispatch", "takeover")
        or not isinstance(task_id, str)
        or not task_id.strip()
        or row.get("scope") == "route"
    ):
        raise LbError(
            "observation action must be dispatch or takeover on a task observation",
            EXIT_REFUSED,
        )


def _section(text):
    lines = text.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    headings = [
        (index, line)
        for index, line in visible_lines(lines)
        if line is not None and NEXT_HEADING.match(line)
    ]
    matches = [
        i
        for i, (_, line) in enumerate(headings)
        if HEADINGS.fullmatch(line.rstrip("\n"))
    ]
    if len(matches) > 1:
        raise LbError("duplicate route readiness evidence sections", EXIT_REFUSED)
    if not matches:
        return None
    i = matches[0]
    start = offsets[headings[i][0]]
    end = offsets[headings[i + 1][0]] if i + 1 < len(headings) else len(text)
    return start, end


def _validate(value):
    if not isinstance(value, dict) or set(value) != FIELDS:
        raise LbError("invalid route readiness evidence fields", EXIT_REFUSED)
    if not isinstance(value["run_ref"], str) or not value["run_ref"].strip():
        raise LbError("route evidence requires a run reference", EXIT_REFUSED)
    if any(not isinstance(value[key], list) for key in FIELDS - {"run_ref"}):
        raise LbError("route evidence records must be lists", EXIT_REFUSED)
    if any(
        not isinstance(item, dict)
        for key in FIELDS - {"run_ref"}
        for item in value[key]
    ):
        raise LbError("route evidence records must be objects", EXIT_REFUSED)
    for observation in value["observations"]:
        _validate_observation(observation)


def parse_evidence(text):
    section = _section(text)
    if section is None:
        return None
    content = text[section[0] : section[1]]
    match = re.fullmatch(
        r"## 路线确认与预检[ \t]*\r?\n\s*```json\r?\n(.*?)\r?\n```[ \t]*\s*",
        content,
        re.DOTALL,
    )
    if not match:
        raise LbError("invalid route readiness evidence section", EXIT_REFUSED)
    try:
        value = json.loads(match.group(1), object_pairs_hook=unique_object)
    except (ValueError, TypeError) as exc:
        raise LbError("invalid route readiness evidence JSON", EXIT_REFUSED) from exc
    _validate(value)
    return value


def replace_evidence(text, value):
    _validate(value)
    section = _section(text)
    if section is not None and parse_evidence(text) == value:
        return text
    newline = "\r\n" if "\r\n" in text else "\n"
    serialized = json.dumps(value, ensure_ascii=False, indent=2).replace("\n", newline)
    replacement = f"{HEADING}{newline}{newline}```json{newline}{serialized}{newline}```{newline}{newline}"
    if section is None:
        prefix = text
        if prefix and not prefix.endswith(("\n", "\r")):
            prefix += newline
        if prefix and not prefix.endswith(newline * 2):
            prefix += newline
        return prefix + replacement
    return text[: section[0]] + replacement + text[section[1] :]


def merge_evidence(previous, proposed, run_id):
    """Accept a replacement only if it retains the run and its recorded history."""
    _validate(proposed)
    if proposed["run_ref"] != run_id or (
        previous is not None and previous["run_ref"] != run_id
    ):
        raise LbError("route evidence belongs to a different run", EXIT_REFUSED)
    if previous is not None and any(
        proposed[key][: len(previous[key])] != previous[key]
        for key in FIELDS - {"run_ref"}
    ):
        raise LbError(
            "route evidence history changed; reread before updating", EXIT_REFUSED
        )
    for key in ("confirmations", "observations", "grants"):
        # Preserve previously saved history, including sources older writers accepted.
        first_new = len(previous[key]) if previous is not None else 0
        for index, row in enumerate(proposed[key][first_new:], start=first_new + 1):
            source = row.get("source")
            if not isinstance(source, str) or not source.strip():
                raise LbError(
                    f"route evidence {key} record {index} source must be a nonempty string",
                    EXIT_REFUSED,
                )
        active_records(key, proposed[key])
    return proposed


def bound_thinking(doc, identity, thinking):
    path = safe_path(doc.root, thinking, field="--thinking")
    unified.companion_key(doc.root, doc.path, path, identity, thinking)
    return path


def read_bound_evidence(doc, identity):
    base = state.project(doc.path, doc.root)
    if doc.path.relative_to(base).as_posix() != identity["log_path"]:
        raise LbError("route evidence requires the run's Logbook", EXIT_REFUSED)
    evidence = []
    field = "identity.document_paths"
    for name in identity["document_paths"]:
        if name == identity["log_path"]:
            continue
        path = state.project_file(base, name, field)
        if path != base / name:
            raise path_error(field, name, base, "bound document path changed")
        value = parse_evidence(_read_thinking(base, path, field, name).decode())
        if value is not None:
            evidence.append(value)
    if len(evidence) == 1 and evidence[0]["run_ref"] == identity["run_id"]:
        return evidence[0]
    return None


def _read_thinking(base, path, field, original):
    try:
        return state.read_regular(base, path)
    except OSError as exc:
        raise path_error(field, original, base, f"cannot read bound document: {exc}") from exc


def current_records(records, task_id, route_ref, scope_ref):
    return [
        row
        for row in records
        if (
            (
                row.get("scope") == task_id
                and scope_ref is not None
                and row.get("route_ref") == scope_ref
            )
            or (
                row.get("scope") in (None, "route")
                and row.get("route_ref") == route_ref
            )
        )
        and isinstance(row.get("source"), str)
        and row["source"].strip()
    ]


def update_evidence(doc, thinking, proposed, dry_run=False):
    from logbook_cli.repository import edit_document, markdown_document, sync_status

    _, run = unified.locate(doc.root, doc.path, required=True)
    path = bound_thinking(doc, run["identity"], thinking)
    data = _read_thinking(doc.root, path, "--thinking", thinking)
    target = markdown_document(data, path, doc.root)
    target.sync_status = sync_status(target, run)
    previous = parse_evidence(target.text)
    value = merge_evidence(previous, proposed, run["identity"]["run_id"])
    first_new = len(previous["observations"]) if previous is not None else 0
    base = state.project(doc.path, doc.root)
    field = "observations.inputs"
    for row in value["observations"][first_new:]:
        inputs = row.get("inputs", {})
        if not isinstance(inputs, dict):
            raise LbError(
                f"{field} (root {base}): expected a map of project-relative file keys",
                EXIT_REFUSED,
            )
        for name in inputs:
            state.project_relative_path(base, name, field)
    changed = replace_evidence(target.text, value)
    return edit_document(target, changed, dry_run)


def active_records(kind, records):
    scope_keys = {
        "confirmations": ("scope",),
        "observations": ("scope", "task_id", "object", "action"),
        "grants": ("scope", "task_id", "actor", "action"),
    }[kind]
    active = []
    by_id = {}
    replaced = set()
    for row in records:
        if kind == "observations":
            _validate_observation(row)
        identity = row.get("id")
        predecessor = row.get("supersedes")
        if "id" in row and (not isinstance(identity, str) or not identity.strip()):
            raise LbError("invalid route evidence record ID", EXIT_REFUSED)
        if identity is not None and identity in by_id:
            if by_id[identity] != row:
                raise LbError(
                    "route evidence record ID already has different content",
                    EXIT_REFUSED,
                )
            continue
        if "supersedes" in row:
            if (
                identity is None
                or not isinstance(predecessor, str)
                or predecessor not in by_id
                or predecessor in replaced
                or any(
                    row.get(key) != by_id[predecessor].get(key) for key in scope_keys
                )
            ):
                raise LbError(
                    "route evidence replacement must identify an active record in the same scope",
                    EXIT_REFUSED,
                )
            replaced.add(predecessor)
        if identity is not None:
            by_id[identity] = row
        active.append(row)
    return [row for row in active if row.get("id") not in replaced]
