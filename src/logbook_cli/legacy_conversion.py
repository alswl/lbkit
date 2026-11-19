"""Build a unified candidate from a verified legacy inventory."""

import hashlib
import json
import re
from graphlib import CycleError, TopologicalSorter

from logbook_cli import (
    execution,
    link_records,
    observation,
    records,
    state,
    task_identity,
    unified,
)
from logbook_cli.adapters import herdr
from logbook_cli.document import EXIT_REFUSED, LbError, parse_text
from logbook_cli.lifecycle import get as lifecycle
from logbook_cli.models import Field
from logbook_cli.repository import markdown_document, project_document
from logbook_cli.run_metrics import calculate
from logbook_cli.services import closeout, dispatches, skill_capabilities
from logbook_cli.services.transport import (
    DISPATCH_BINDING_FIELDS,
    DISPATCH_PACKAGE_FIELDS,
    legacy_digest,
)
from logbook_cli.task_records import hydrate, valid_resolution


def refuse(message):
    raise LbError(message, EXIT_REFUSED)


def checksum(data):
    return hashlib.sha256(data).hexdigest()


def source_snapshot(root, project, inventory):
    paths = {
        (project / name).relative_to(root).as_posix()
        for name in inventory["identity"]["document_paths"]
    }
    sources = inventory["sources"]
    paths.update(row["path"] for row in sources["sidecars"])
    paths.update(
        sources[key]["path"] for key in ("execution", "monitoring") if sources[key]
    )
    return {name: state.read_regular(root, root / name) for name in sorted(paths)}


TASK_HISTORY_FIELDS = {"basis", "history", "resolution"}


def validate_task_history(key, row):
    if "basis" in row and (
        not isinstance(row["basis"], str)
        or not row["basis"].strip()
        or any(c in row["basis"] for c in "\r\n")
    ):
        refuse(f"invalid legacy Task basis: {key}")
    if "history" in row and (
        not isinstance(row["history"], list)
        or any(not isinstance(entry, dict) for entry in row["history"])
    ):
        refuse(f"invalid legacy Task history: {key}")


def validate_task_resolution(key, old, current, value):
    if not valid_resolution(value, old) or any(
        field in value
        and (
            not isinstance(value[field], str)
            or not value[field].strip()
            or any(c in value[field] for c in "\r\n")
        )
        for field in ("actor", "source")
    ):
        refuse(f"invalid or stale legacy Resolution: {key}")
    if not any(a.kind is Field.RESOLUTION for a in current.annotations):
        refuse(f"legacy Resolution is missing from Markdown: {key}")
    expected = {
        "task": value["task"],
        "as": value["as"],
        **{
            field: value[field].replace("<", "&lt;").replace(">", "&gt;")
            for field in ("decision", "note")
        },
    }
    if current.resolution_error or current.resolution != expected:
        refuse(f"legacy Resolution differs from Markdown: {key}")


def document_state(root, project, relative, data, groups):
    path = project / relative
    if path.suffix != ".md":
        refuse(f"migration supports Markdown documents only: {relative}")
    old = parse_text(data, path, root)
    old.metadata = groups
    current = markdown_document(data, path, root)
    if lifecycle(old)["value"] != lifecycle(current)["value"]:
        refuse(f"legacy lifecycle differs from Markdown: {relative}")
    legacy_tasks = task_identity.bindings(old)
    current_tasks = task_identity.bindings(current)
    for key, (task, _, row) in legacy_tasks.items():
        validate_task_history(key, row)
        current_task = current_tasks[key][0]
        if "resolution" in row:
            validate_task_resolution(key, task, current_task, row["resolution"])
        elif current_task.resolution is not None:
            refuse(
                f"legacy Resolution record is missing for Markdown disposition: {key}"
            )
    hydrate(old)

    projected = project_document(data, path, root)
    for key, (task, _, row) in legacy_tasks.items():
        snapshot = task_identity.snapshot(task, row)
        if (
            set(row) - {"id", "status", "depends_on"} - TASK_HISTORY_FIELDS
            or not snapshot["consistent"]
            or snapshot["status"] != projected["tasks"][key]["effective_state"]
            or snapshot["depends_on"] != projected["tasks"][key]["dependencies"]
        ):
            refuse(f"legacy Task {key} has facts without a Markdown equivalent")
    return projected


TASK_ID = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,63}")
SHA256 = re.compile(r"[0-9a-f]{64}")


def verification_history(doc, rows):
    # The historical decoder checks data and record digests without locating or fetching links.
    _, errors, _ = link_records.comment_records(doc)
    if errors:
        refuse(f"invalid legacy link verification: {errors[0]['reason']}")
    for key, row in rows.items():
        digest = row["binding"]
        if (
            (row["bound_task"] is None) != (digest is None)
            or not SHA256.fullmatch(row["anchor"])
            or (digest is not None and not SHA256.fullmatch(digest))
            or (
                "local_digest" in row
                and (
                    not isinstance(row["local_digest"], str)
                    or not SHA256.fullmatch(row["local_digest"])
                )
            )
        ):
            refuse(f"ambiguous legacy link verification binding: {key}")


def archive_history(doc, rows):
    for key, row in rows.items():
        if key in doc.metadata.get("task-archive", {}):
            refuse(f"legacy Task archive also exists in Markdown: {key}")
        replacements = row.get("replacement_ids")
        if (
            not TASK_ID.fullmatch(key)
            or row.get("id") != key
            or any(
                not isinstance(row.get(field), str) or not row[field].strip()
                for field in ("content", "basis", "previous_text")
            )
            or not isinstance(replacements, list)
            or len(replacements) < 2
            or any(
                not isinstance(item, str) or not TASK_ID.fullmatch(item)
                for item in replacements
            )
            or len(set(replacements)) != len(replacements)
            or key in replacements
        ):
            refuse(
                f"invalid legacy Task archive identity, content or replacements: {key}"
            )
        if "replacement_texts" in row and (
            not isinstance(row["replacement_texts"], list)
            or len(row["replacement_texts"]) != len(replacements)
            or any(
                not isinstance(text, str) or not text.strip()
                for text in row["replacement_texts"]
            )
        ):
            refuse(f"invalid legacy Task archive replacement texts: {key}")

        original = parse_text(
            (
                "# Archived package\n\n## Stage 01 Archived\n\n" + row["content"]
            ).encode(),
            doc.path,
            doc.root,
        )
        tasks = [task for stage in original.stages for task in stage.tasks]
        anchors = records.anchors(original, require_closed=True)
        if (
            len(tasks) != 1
            or tasks[0].text != row["previous_text"]
            or [identifier for _, identifier in anchors] not in ([], [key])
            or (
                "previous_task_digest" in row
                and row["previous_task_digest"] != tasks[0].identity
            )
        ):
            refuse(f"legacy Task archive original does not match its identity: {key}")


def validate_archive_references(documents, history):
    owners: dict[str, str] = {}
    active: dict[str, set[str]] = {}
    for name, projection in documents.items():
        for key in projection["tasks"]:
            active.setdefault(key, set()).add(name)
    for name, groups in history.items():
        for key in groups.get("task-archive", {}):
            if key in active:
                refuse(f"historical Task ID is active: {key}")
            if key in owners:
                refuse(f"historical Task ID has multiple owners: {key}")
            owners[key] = name
    for name, groups in history.items():
        archives = groups.get("task-archive", {})
        for key, row in archives.items():
            for replacement in row["replacement_ids"]:
                if owners.get(replacement) != name and active.get(replacement) != {
                    name
                }:
                    refuse(
                        f"legacy Task archive {key} has an unverified replacement: {replacement}"
                    )

        graph = {
            key: [
                replacement
                for replacement in row["replacement_ids"]
                if replacement in archives
            ]
            for key, row in archives.items()
        }
        try:
            TopologicalSorter(graph).prepare()
        except CycleError as exc:
            raise LbError(
                f"legacy Task archive replacement cycle: {', '.join(exc.args[1])}",
                EXIT_REFUSED,
            ) from exc


def validate_coordination_history(doc, log, task_ids):
    try:
        events = closeout.state_events(doc)
        scopes: dict[str, set[str]] = {}
        for event in events:
            scopes.setdefault(event["run_id"], {"logbook"}).add(event["scope"])
        for run, selected in scopes.items():
            for scope in sorted(selected):
                calculate(events, run, scope)
    except (ValueError, TypeError, KeyError) as exc:
        raise LbError(f"invalid legacy run-event history: {exc}", EXIT_REFUSED) from exc

    for key, row in doc.metadata.get("skill-usage", {}).items():
        try:
            if (
                row.get("id") != key
                or row.get("log") != log
                or not isinstance(row.get("task_id"), str)
                or row["task_id"] not in task_ids
                or not isinstance(row.get("definition_digest"), str)
                or not SHA256.fullmatch(row["definition_digest"])
            ):
                raise ValueError("unverified Logbook, Task or definition digest")
            skill_capabilities.validate_usage_payload(
                {
                    name: value
                    for name, value in row.items()
                    if name not in {"log", "definition_digest"}
                }
            )
        except (LbError, ValueError, TypeError) as exc:
            detail = exc.message if isinstance(exc, LbError) else str(exc)
            raise LbError(
                f"invalid legacy skill usage {key}: {detail}", EXIT_REFUSED
            ) from exc


def historical_time(value):
    records.single_line(value, "at")
    records.observed(value)
    return link_records.timestamp(value)


def closed_attempts(key, dispatch):
    """Accept a full closeout chain and terminal attempts belonging to it."""
    expected = [
        ("prepared", "sent"),
        ("sent", "acknowledged"),
        ("acknowledged", "returned"),
        ("returned", "closed"),
    ]
    history = dispatch["history"]
    try:
        if dispatch["status"] != "closed" or len(history) != len(expected):
            raise ValueError(
                "requires a closed Dispatch with its complete transition history"
            )
        for transition, edge in zip(history, expected):
            if (
                not isinstance(transition, dict)
                or set(transition) != {"from", "to", "basis", "at"}
                or (transition["from"], transition["to"]) != edge
            ):
                raise ValueError("unverified Dispatch transition")
            records.single_line(transition["basis"], "basis")
        times = [historical_time(row["at"]) for row in history]
        if times != sorted(times):
            raise ValueError("Dispatch transitions are out of time order")
        previous_end = times[1]
        attempts: list[str] = []
        for attempt in dispatch["attempts"]:
            if (
                not isinstance(attempt, dict)
                or set(attempt) != {"id", "status", "basis", "started_at", "ended_at"}
                or attempt["status"] not in {"finished", "failed", "interrupted"}
            ):
                raise ValueError(
                    "Attempt must have its recorded terminal state and endpoints"
                )
            records.single_line(attempt["id"], "attempt ID")
            records.single_line(attempt["basis"], "basis")
            start = historical_time(attempt["started_at"])
            end = historical_time(attempt["ended_at"])
            if (
                attempt["id"] in attempts
                or not previous_end <= start <= end <= times[2]
            ):
                raise ValueError("Attempt identity, order or time bounds are ambiguous")
            attempts.append(attempt["id"])
            previous_end = end
        return attempts
    except (LbError, ValueError, TypeError, KeyError) as exc:
        detail = exc.message if isinstance(exc, LbError) else str(exc)
        raise LbError(
            f"unsupported attempts for legacy Dispatch {key}: {detail}", EXIT_REFUSED
        ) from exc


def owned_dispatches(log, run_id, tasks, archived_tasks, thinking):
    by_id = thinking.get("dispatch", {})
    attempts = {}
    for key, row in by_id.items():
        if (
            row.get("log") != log
            or row.get("log_id") != run_id
            or not isinstance(row.get("task_id"), str)
            or row["task_id"] not in tasks | archived_tasks
            or row.get("status") not in dispatches.TRANSITIONS
            or not isinstance(row.get("attempts"), list)
            or not isinstance(row.get("history"), list)
            or any(
                not isinstance(row.get(field), str) or not row[field].strip()
                for field in DISPATCH_PACKAGE_FIELDS
            )
        ):
            refuse(f"unverified legacy Dispatch or unsupported attempts: {key}")
        if row["attempts"]:
            attempts[key] = closed_attempts(key, row)
        elif (
            row["status"] in {"acknowledged", "returned", "closed"}
            or row["task_id"] in archived_tasks
        ):
            refuse(f"legacy Dispatch {key} lacks a verified terminal Attempt")
    for key, binding in thinking.get("agent", {}).items():
        row = by_id.get(key)
        if (
            row is None
            or binding.get("log") != log
            or binding.get("log_id") != run_id
            or binding.get("task_id") != row["task_id"]
        ):
            refuse(f"unverified legacy agent binding: {key}")
        try:
            herdr.validate_binding(
                {
                    name: value
                    for name, value in binding.items()
                    if name not in {"id", "log", "log_id", "task_id"}
                }
            )
        except (LbError, ValueError, TypeError) as exc:
            raise LbError(f"invalid legacy agent binding: {key}", EXIT_REFUSED) from exc
    return by_id, attempts


def runtime_records(log, run_id, tasks, archived_tasks, old, groups):
    final = {"tasks": {}, "operations": {}, "facts": []}
    if old is None:
        return final
    final.update(
        captain=old["captain"], advancement=old["advancement"], facts=old["facts"]
    )
    by_id, attempts = owned_dispatches(log, run_id, tasks, archived_tasks, groups)
    delivered = set()
    attempted_dispatches = set()
    represented = set()
    for op in old["operations"]:
        request = op["request"]
        key = request["dispatch_id"]
        row = by_id.get(key)
        binding = groups.get("agent", {}).get(key)
        if (
            row is None
            or binding is None
            or request.get("task_id", row["task_id"]) != row["task_id"]
            or row["owner"] != request["recipient"]
            or binding.get("session_id") != request["session_id"]
            or legacy_digest(row, DISPATCH_PACKAGE_FIELDS) != request["package_digest"]
            or legacy_digest(binding, DISPATCH_BINDING_FIELDS)
            != request["binding_digest"]
        ):
            refuse(f"unverified Dispatch/Task mapping for send {op['id']}: {key}")
        represented.add(key)
        if op["outcome"] in ("unknown", "submitted"):
            if key in delivered:
                refuse(f"ambiguous legacy delivery history: {key}")
            delivered.add(key)
        imported = dict(op, legacy_task_id=row["task_id"])
        if key in attempts and op["outcome"] != "not_submitted":
            evidence = op["receipt"]
            if (
                op["outcome"] != "submitted"
                or not isinstance(evidence, dict)
                or (
                    op["provenance"] == "caller_reported_runtime_observation"
                    and (
                        not isinstance(evidence.get("evidence_ref"), str)
                        or not evidence["evidence_ref"].strip()
                    )
                )
            ):
                refuse(
                    f"terminal legacy Attempt requires a verified submitted delivery: {key}"
                )
            imported["legacy_attempt_ids"] = attempts[key]
            attempted_dispatches.add(key)
        final["operations"][op["id"]] = imported
    if set(attempts) - attempted_dispatches:
        refuse(
            f"legacy terminal Attempt has no matched submitted delivery: {min(set(attempts) - attempted_dispatches)}"
        )
    for key, row in by_id.items():
        if key in delivered or (row["status"] == "prepared" and key in represented):
            continue
        if (
            row["status"] not in {"prepared", "cancelled"}
            or row["history"]
            or key in groups.get("agent", {})
        ):
            refuse(f"legacy Dispatch {key} lacks attributable delivery history")
    for fact in old["facts"]:
        if (
            fact["kind"] in {"condition-result", "delegation-release", "handoff"}
            or fact.get("release_condition") is not None
        ):
            refuse(
                f"legacy release or handoff needs explicit reconciliation: {fact['id']}"
            )
        if fact["kind"] in {"business-action", "transport-resolution"}:
            op = final["operations"].get(fact["operation_id"])
            if (
                op is not None
                and op.get("legacy_attempt_ids")
                and fact["kind"] == "business-action"
                and fact["outcome"] == "not_started"
            ):
                refuse(
                    f"legacy no-start claim conflicts with a terminal Attempt: {fact['id']}"
                )
            if op is None or op["outcome"] not in (
                ("submitted",)
                if fact["kind"] == "business-action"
                else (fact["outcome"],)
            ):
                refuse(f"legacy fact conflicts with its send: {fact['id']}")
    return final


def candidate(root, project, inventory, snapshot):
    identity = inventory["identity"]
    run_id = identity["proposed_run_id"]
    if run_id is None:
        refuse("migration requires a verified Logbook UUID")
    relative_log = identity["log_path"]
    documents = {}
    source = inventory["sources"]
    old = None
    if source["execution"]:
        name = source["execution"]["path"]
        old = execution.validate(
            json.loads(snapshot[name], object_pairs_hook=state.unique_object),
            root / name,
        )
    metadata = {}
    history = {}
    for row in source["sidecars"]:
        if row["unselected_sections"]:
            refuse("migration cannot switch a sidecar shared with unselected documents")
        sections = json.loads(
            snapshot[row["path"]], object_pairs_hook=state.unique_object
        )["documents"]
        for relative, groups in sections.items():
            state.validate(groups)
            if (
                identity["document_uuids"].get(relative)
                != groups["document"]["identity"]["uuid"]
            ):
                refuse("legacy document identity changed during planning")
            allowed = {
                "document",
                "task",
                "lifecycle",
                "link-verification",
                "task-archive",
            }
            if old and relative == old["thinking"]:
                allowed.update(("dispatch", "agent", "run-event", "skill-usage"))
            unsupported = set(groups) - allowed
            if unsupported:
                refuse(
                    f"legacy records need explicit reconciliation in {relative}: {', '.join(sorted(unsupported))}"
                )
            metadata[relative] = groups
    for relative in identity["document_paths"]:
        path = (project / relative).relative_to(root).as_posix()
        documents[relative] = document_state(
            root, project, relative, snapshot[path], metadata.get(relative, {})
        )

    for relative, groups in metadata.items():
        links = groups.get("link-verification", {})
        archives = groups.get("task-archive", {})
        retained = {
            kind: groups[kind]
            for kind in (
                "link-verification",
                "task-archive",
                "dispatch",
                "agent",
                "run-event",
                "skill-usage",
            )
            if groups.get(kind)
        }
        task_history = {
            key: row
            for key, row in groups.get("task", {}).items()
            if TASK_HISTORY_FIELDS.intersection(row)
        }
        if task_history:
            retained["task"] = task_history
        if not retained:
            continue
        path = project / relative
        data = snapshot[path.relative_to(root).as_posix()]
        if links:
            old_doc = parse_text(data, path, root)
            old_doc.metadata = groups
            verification_history(old_doc, links)
        if archives:
            archive_history(markdown_document(data, path, root), archives)
        history[relative] = retained
    validate_archive_references(documents, history)

    log_path = project / relative_log
    legacy_log = parse_text(
        snapshot[log_path.relative_to(root).as_posix()], log_path, root
    )
    if (
        not old or not any(fact["kind"] == "takeover" for fact in old["facts"])
    ) and any(
        field.kind is Field.STATUS and "👨‍✈️" in field.value
        for stage in legacy_log.stages
        for task in stage.tasks
        for field in task.annotations
    ):
        refuse("legacy Captain marker requires attributable takeover facts")
    if old and (
        old["log"] != relative_log or old["thinking"] != source["execution"]["thinking"]
    ):
        refuse("legacy execution binding changed during planning")
    log = log_path.relative_to(root).as_posix()
    tasks = set(documents[relative_log]["tasks"])
    archived_tasks = set(metadata.get(relative_log, {}).get("task-archive", {}))
    groups = metadata.get(old["thinking"], {}) if old else {}
    other_task_ids = {
        key
        for relative, projection in documents.items()
        if relative != relative_log
        for key in projection["tasks"]
    }
    for row in groups.get("dispatch", {}).values():
        key = row.get("task_id")
        if isinstance(key, str) and key in tasks and key in other_task_ids:
            refuse(f"legacy Dispatch Task ID also belongs to another document: {key}")
    if old and (groups.get("run-event") or groups.get("skill-usage")):
        path = project / old["thinking"]
        thinking = parse_text(snapshot[path.relative_to(root).as_posix()], path, root)
        thinking.metadata = groups
        validate_coordination_history(thinking, log, tasks | archived_tasks)
    runtime = runtime_records(log, run_id, tasks, archived_tasks, old, groups)
    monitor = None
    if source["monitoring"]:
        monitor = observation.decode_for_migration(
            snapshot[source["monitoring"]["path"]]
        )
        if monitor["id"] != source["monitoring"]["observation_id"]:
            refuse("legacy observation identity changed during planning")
    return {
        "format": unified.FORMAT,
        "identity": {key: identity[key] for key in ("log_path", "document_paths")}
        | {"run_id": run_id},
        "documents": documents,
        "execution": runtime,
        "monitoring": monitor,
        **({"legacy_history": history} if history else {}),
    }
