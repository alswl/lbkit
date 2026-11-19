"""Read-only inventory for an explicitly selected legacy run."""

import fcntl
import hashlib
import os
import re

from logbook_cli import execution, observation, state, unified
from logbook_cli.document import EXIT_REFUSED, LbError, root_path
from logbook_cli.services.common import Result

PREVIEW_ONLY = "Migration apply is unavailable. This preview cannot be executed."


def document(root, raw):
    path = root / raw
    if not path.is_relative_to(root) or ".." in path.parts:
        raise LbError("migration document must stay inside --root", EXIT_REFUSED)
    try:
        with state.open_regular(root, path):
            pass
    except OSError as exc:
        raise LbError(
            f"missing or unsafe migration document: {raw}", EXIT_REFUSED
        ) from exc
    return path


def sidecar_sources(root, directory, paths):
    """Locate exact sections and prove ownership of the selected UUIDs."""
    expected = {path.relative_to(directory.parent).as_posix(): path for path in paths}
    owners: dict[str, int] = {}
    selected = {}
    sources = []
    for path in sorted(directory.glob("*.md.json")):
        _, sections = state.read_file(path, root=root)
        owned = []
        for relative, groups in sections.items():
            identity = groups["document"]["identity"]["uuid"]
            key = identity.lower()
            owners[key] = owners.get(key, 0) + 1
            if relative not in expected:
                if any(
                    execution.matches_binding(directory.parent, relative, p)
                    for p in paths
                ):
                    raise LbError("noncanonical legacy document section", EXIT_REFUSED)
                continue
            if path != state.path_for(expected[relative], root):
                raise LbError(
                    "legacy document section is in the wrong sidecar", EXIT_REFUSED
                )
            if not re.fullmatch(r"[0-9a-f]{32}", identity):
                raise LbError("invalid legacy document UUID", EXIT_REFUSED)
            selected[relative] = identity
            owned.append(relative)
        if owned:
            sources.append(
                {
                    "path": str(path.relative_to(root)),
                    "documents": sorted(owned),
                    "unselected_sections": len(sections) - len(owned),
                    "record_counts": {
                        relative: {
                            kind: len(rows) for kind, rows in sections[relative].items()
                        }
                        for relative in sorted(owned)
                    },
                }
            )
        elif any(path == state.path_for(p, root) for p in paths):
            raise LbError(
                "legacy sidecar has no selected document section", EXIT_REFUSED
            )
    for identity in selected.values():
        if owners[identity] != 1:
            raise LbError("legacy document UUID has multiple owners", EXIT_REFUSED)
    return sources, dict(sorted(selected.items()))


def is_present(root, path):
    try:
        with state.open_regular(root, path):
            return True
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise LbError(
            f"unsafe migration path: {path.relative_to(root)}", EXIT_REFUSED
        ) from exc


def exclusive_lock_held(fd):
    # A transient shared lock probes existing exclusivity without creating a file.
    try:
        fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
    except BlockingIOError:
        return True
    return False


def lock_busy(root, path):
    try:
        with state.open_regular(root, path) as handle:
            return exclusive_lock_held(handle.fileno())
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise LbError(
            f"unsafe migration lock: {path.relative_to(root)}", EXIT_REFUSED
        ) from exc


def indexed(rows, statuses, status_key):
    result = {}
    for row in rows:
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("id"), str)
            or not row["id"].strip()
            or row["id"] in result
            or row.get(status_key) not in statuses
            or not isinstance(row.get("history"), list)
        ):
            raise ValueError("ambiguous or invalid observation history")
        result[row["id"]] = row
    return result


def monitoring_source(root, log, directory, uuid, conflicts):
    folder = directory / "observations"
    if folder.is_symlink() or (folder.exists() and not folder.is_dir()):
        raise LbError("unsafe legacy observations directory", EXIT_REFUSED)
    fallback = folder / (str(log.relative_to(root)) + ".json")
    if any(
        is_present(root, path) for path in (fallback, fallback.with_suffix(".listener"))
    ):
        raise LbError(
            "legacy observation without a verified document UUID binding", EXIT_REFUSED
        )
    if uuid is None:
        return None
    path = folder / (uuid + ".json")
    listener_lock = path.with_suffix(".listener")
    if lock_busy(root, listener_lock):
        conflicts.append(
            {"code": "listener_busy", "path": str(listener_lock.relative_to(root))}
        )
    for action in sorted(folder.glob(f"{uuid}.action-*")):
        if lock_busy(root, action):
            conflicts.append(
                {"code": "action_busy", "path": str(action.relative_to(root))}
            )
    try:
        data = state.read_regular(root, path, observation.STATE_LIMIT)
        value = observation.decode_for_migration(data)
        from logbook_cli.services.agent_wait import EVENT_KINDS, encoded

        events = indexed(
            value["events"], ("pending", "deferred", "resolved"), "handling"
        )
        answers = indexed(
            value["answers"],
            ("unknown", "submitted", "confirmed", "not_submitted"),
            "status",
        )
        for key, row in events.items():
            event = row.get("observation")
            if (
                not isinstance(event, dict)
                or not isinstance(event.get("binding"), dict)
                or not isinstance(event.get("event_id"), str)
                or not event["event_id"]
                or event.get("kind") not in EVENT_KINDS
            ):
                raise ValueError("invalid Event ownership")
            binding = hashlib.sha256(encoded(event["binding"])).hexdigest()
            if key != f"{value['id']}:{binding}:{event['event_id']}":
                raise ValueError("inconsistent Event identity")
        for row in answers.values():
            event = events.get(row.get("event_id"))
            if (
                event is None
                or event["observation"]["binding"] != row.get("binding")
                or (
                    row["status"] in ("unknown", "submitted")
                    and (
                        event["handling"] == "resolved"
                        or event["observation"].get("kind") != "needs_input"
                    )
                )
            ):
                raise ValueError("invalid Answer ownership or pending state")
        listener = value.get("listener")
        if listener is not None and (
            not isinstance(listener, dict)
            or listener.get("status") not in ("active", "ended")
            or not isinstance(listener.get("invocation_id"), str)
            or not listener["invocation_id"]
            or type(listener.get("generation")) is not int
            or listener["generation"] < 1
        ):
            raise ValueError("invalid saved listener state")
        retired = value.get("retired", {})
        if not isinstance(retired, dict):
            raise ValueError("invalid retired observations")
        observation.admit(value, new_work=False)
    except FileNotFoundError:
        return None
    except (OSError, ValueError, TypeError, LbError) as exc:
        detail = exc.message if isinstance(exc, LbError) else str(exc)
        raise LbError(f"invalid legacy observation: {detail}", EXIT_REFUSED) from exc
    if listener is not None and listener["status"] == "active":
        conflicts.append(
            {"code": "saved_listener_active", "path": str(path.relative_to(root))}
        )
    return {
        "path": str(path.relative_to(root)),
        "document_uuid": uuid,
        "observation_id": value["id"],
        "listener": (
            {key: listener[key] for key in ("invocation_id", "generation", "status")}
            if listener is not None
            else None
        ),
        "targets": len(value["targets"]),
        "cursors": len(value["cursors"]),
        "revision": value["revision"],
        "retired_targets": len(retired),
        "events": len(events),
        "answers": len(answers),
        "unresolved_events": [
            {"id": key, "handling": row["handling"]}
            for key, row in events.items()
            if row["handling"] != "resolved"
        ],
        "pending_answers": [
            {"id": key, "status": row["status"], "event_id": row["event_id"]}
            for key, row in answers.items()
            if row["status"] in ("unknown", "submitted")
        ],
    }


def preview(root, log, name, documents, *, writers_locked=False):
    base = root_path(root)
    log_path = document(base, log)
    unified.validate_name(name)
    project = state.project(log_path, base)
    directory = state.directory(log_path, base)
    target = directory / (name + ".json")
    old_path, _, old = execution.find_legacy(base, log_path)
    paths = {log_path, *(document(base, path) for path in documents)}
    if old is not None:
        paths.add(project / old["thinking"])
    for path in sorted(paths):
        if state.project(path, base) != project:
            raise LbError(
                "migration documents must belong to the same project", EXIT_REFUSED
            )
        if unified.locate(base, path)[0] is not None:
            raise LbError("migration document already belongs to a unified run", EXIT_REFUSED)
        bound = execution.find_legacy(base, path, include_thinking=True)[0]
        if bound is not None and bound != old_path:
            raise LbError("document is bound to another legacy execution", EXIT_REFUSED)

    sidecars, document_ids = sidecar_sources(base, directory, paths)
    relative_log = log_path.relative_to(project).as_posix()
    run_id = document_ids.get(relative_log)
    relative_paths = sorted(p.relative_to(project).as_posix() for p in paths)
    for _, value in unified.runs(base, directory):
        identity = value["identity"]
        if set(relative_paths).intersection(identity["document_paths"]):
            raise LbError(
                "migration document already belongs to a unified run", EXIT_REFUSED
            )
        if run_id == identity["run_id"]:
            raise LbError("legacy run UUID is already in use", EXIT_REFUSED)

    conflicts = []
    if not writers_locked:
        fd = os.open(base, os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY)
        try:
            if exclusive_lock_held(fd):
                conflicts.append({"code": "legacy_writer_busy", "path": "."})
        finally:
            os.close(fd)
        writer_lock = directory / ".lock"
        if lock_busy(base, writer_lock):
            conflicts.append(
                {"code": "writer_busy", "path": str(writer_lock.relative_to(base))}
            )
    if is_present(base, target):
        conflicts.append(
            {
                "code": "target_is_legacy_execution"
                if target == old_path
                else "target_exists",
                "path": str(target.relative_to(base)),
            }
        )
    journal_owners = paths | ({old_path} if old_path is not None else set())
    for journal in sorted({state.journal_for(path, base) for path in journal_owners}):
        if is_present(base, journal):
            conflicts.append(
                {"code": "legacy_transaction", "path": str(journal.relative_to(base))}
            )

    monitoring = monitoring_source(base, log_path, directory, run_id, conflicts)
    for relative, uuid in document_ids.items():
        if relative != relative_log:
            path = directory / "observations" / (uuid + ".json")
            if is_present(base, path):
                conflicts.append(
                    {
                        "code": "associated_document_observation",
                        "path": str(path.relative_to(base)),
                    }
                )
    log_journal = str(state.journal_for(log_path, base).relative_to(base))
    if (
        run_id is None
        and old is None
        and not any(
            row["code"] == "legacy_transaction" and row["path"] == log_journal
            for row in conflicts
        )
    ):
        raise LbError("no legacy sources bind this Logbook", EXIT_REFUSED)

    history = None
    if old is not None:
        policy = execution.projection(old)
        history = {
            "path": str(old_path.relative_to(base)),
            "name": old["name"],
            "thinking": old["thinking"],
            "advancement": old["advancement"],
            "captain": old["captain"],
            "reported_owner": policy["reported_owner"],
            "delegation_restricted": policy["restricted"],
            "facts": [
                {"id": fact["id"], "kind": fact["kind"]} for fact in old["facts"]
            ],
            "operations": [
                {
                    "id": op["id"],
                    "dispatch_id": op["request"]["dispatch_id"],
                    "outcome": op["outcome"],
                    "has_receipt": op["receipt"] is not None,
                    "provenance": op["provenance"],
                }
                for op in old["operations"]
            ],
        }

    return Result(
        {
            "dry_run": True,
            "apply_available": False,
            "message": PREVIEW_ONLY,
            "project": str(project.relative_to(base)),
            "target": str(target.relative_to(base)),
            "identity": {
                "log_path": relative_log,
                "document_paths": relative_paths,
                "document_uuids": document_ids,
                "proposed_run_id": run_id,
            },
            "sources": {
                "sidecars": sidecars,
                "execution": history,
                "monitoring": monitoring,
            },
            "conflicts": conflicts,
            "preservation": [
                "Preserve document UUIDs, Task IDs and attributable responsibility and restrictions.",
                "Keep original send intents, outcomes and receipts; reconcile unknown delivery without sending.",
                "Retain monitoring identity, cursors, listener history, Events and pending Answers.",
            ],
        },
        EXIT_REFUSED if conflicts else 0,
    )
