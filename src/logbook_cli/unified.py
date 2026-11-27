"""Single-run storage: rebuildable document projections and independent facts."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import uuid
from contextlib import contextmanager
from pathlib import Path

from logbook_cli import state
from logbook_cli.document import EXIT_REFUSED, LbError
from logbook_cli.run_metrics import event_rows

FORMAT = "task-document-projection"


def validate_name(name):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", name):
        raise LbError("name must be a safe filename component", EXIT_REFUSED)


def encode(value):
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode()


def digest(value):
    return hashlib.sha256(encode(value)).hexdigest()


def read(path, root=None):
    if path.is_symlink():
        raise LbError("unsafe unified state symlink", EXIT_REFUSED)
    try:
        value = state.decode_json(
            state.read_regular(path.parent if root is None else root, path)
        )
        if (
            not isinstance(value, dict)
            or set(value)
            - {
                "legacy_migration", "legacy_history", "preflight",
                "dependency_source", "run_events",
            }
            != {"format", "identity", "documents", "execution", "monitoring"}
            or value["format"] != FORMAT
        ):
            raise ValueError("unsupported state format")
        if "dependency_source" in value and value["dependency_source"] != path.with_suffix(
            ".dependencies.json"
        ).name:
            raise ValueError("invalid dependency source")
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
        if "preflight" in value:
            preflight = value["preflight"]
            if (
                not isinstance(preflight, dict)
                or set(preflight) != {"enrolled", "plans"}
                or not isinstance(preflight["enrolled"], list)
                or not all(
                    isinstance(item, str) and item for item in preflight["enrolled"]
                )
                or len(set(preflight["enrolled"])) != len(preflight["enrolled"])
                or not isinstance(preflight["plans"], dict)
                or set(preflight["plans"]) - set(preflight["enrolled"])
            ):
                raise ValueError("invalid managed preflight state")
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
                or (
                    "legacy_task_id" in operation
                    and (
                        "legacy_migration" not in value
                        or not isinstance(operation["legacy_task_id"], str)
                        or not operation["legacy_task_id"].strip()
                        or "dispatch_id" not in operation["request"]
                        or operation["request"].get(
                            "task_id", operation["legacy_task_id"]
                        ) != operation["legacy_task_id"]
                    )
                )
            ):
                raise ValueError("invalid send operation")
        dispatches = ex.get("monitoring_dispatches", {})
        if not isinstance(dispatches, dict):
            raise ValueError("invalid monitoring dispatches")
        from logbook_cli.wait_state import native_position

        for key, dispatch in dispatches.items():
            if (
                not re.fullmatch(r"[0-9a-f]{64}", key)
                or not isinstance(dispatch, dict)
                or set(dispatch) != {"operation_id", "baseline"}
                or not isinstance(dispatch["operation_id"], str)
            ):
                raise ValueError("invalid monitoring dispatch")
            operation = ex["operations"].get(dispatch["operation_id"], {})
            baseline = dispatch["baseline"]
            if operation.get("outcome") != "submitted" or operation.get("provenance") != "adapter":
                raise ValueError("monitoring dispatch lacks a submitted adapter operation")
            if baseline is not None and (
                not isinstance(baseline, dict) or native_position(baseline) != baseline
            ):
                raise ValueError("invalid monitoring dispatch baseline")
        if "legacy_migration" in value:
            from logbook_cli.legacy_migration import validate_manifest

            validate_manifest(value["legacy_migration"])
        migration = value.get("legacy_migration", {})
        attempts = migration.get("send_attempt_mapping", {})
        expected_attempts = {
            key: operation["legacy_attempt_ids"]
            for key, operation in ex["operations"].items()
            if "legacy_attempt_ids" in operation
        }
        if expected_attempts != attempts or any(
            ex["operations"][key]["outcome"] != "submitted"
            or "legacy_task_id" not in ex["operations"][key]
            for key in attempts
        ):
            raise ValueError("invalid retained legacy Attempt mapping")
        if "legacy_history" in value or "history_sha256" in migration:
            history = value.get("legacy_history")
            if (
                not isinstance(history, dict)
                or not history
                or set(history) - set(identity["document_paths"])
                or any(
                    not isinstance(groups, dict)
                    or not groups
                    or set(groups) - {
                        "link-verification", "task-archive", "dispatch",
                        "agent", "run-event", "skill-usage", "task",
                    }
                    or any(
                        not isinstance(rows, dict) or not rows
                        or any(not isinstance(row, dict) for row in rows.values())
                        for rows in groups.values()
                    )
                    for groups in history.values()
                )
                or digest(history) != migration.get("history_sha256")
            ):
                raise ValueError("invalid retained legacy history")
        streams = value.get("run_events", {})
        if not isinstance(streams, dict) or set(streams) - (
            set(identity["document_paths"]) - {identity["log_path"]}
        ):
            raise ValueError("invalid run-event document associations")
        for rows in streams.values():
            if (
                not isinstance(rows, list)
                or not rows
                or len(event_rows(rows, allow_future=True)) != len(rows)
            ):
                raise ValueError("invalid run-event stream")
        if value["monitoring"] is not None:
            from logbook_cli import observation

            try:
                observation.validate(value["monitoring"])
            except LbError as exc:
                raise ValueError(exc.message) from exc
        return value
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise LbError(
            f"invalid unified state {path.name}: {exc}", EXIT_REFUSED
        ) from exc


def runs(root, directory, *, undecodable_markdown=None):
    for path in sorted(directory.glob("*.json")):
        if path.is_symlink():
            raise LbError("unsafe state symlink", EXIT_REFUSED)
        # Old document sidecars never become new-run inputs.
        if path.name.endswith((".md.json", ".dependencies.json", ".dependencies-transaction.json")):
            continue
        try:
            data = state.read_regular(root, path)
            try:
                raw = state.decode_json(data)
            except ValueError:
                if undecodable_markdown is None or not path.name.endswith(".markdown.json"):
                    raise
                undecodable_markdown.append(path)
                continue
        except (OSError, ValueError) as exc:
            raise LbError(f"invalid state {path.name}", EXIT_REFUSED) from exc
        if isinstance(raw, dict) and raw.get("format") == FORMAT:
            yield path, read(path, root)


def locate(root, log, *, required=False, recovering_dependencies=False):
    directory = state.directory(log, root)
    relative = state.section(log, root)
    undecodable_markdown = []
    matches = [
        (path, value)
        for path, value in runs(root, directory, undecodable_markdown=undecodable_markdown)
        if relative in value["identity"]["document_paths"]
    ]
    if len(matches) > 1:
        raise LbError("multiple run identities bind this document", EXIT_REFUSED)
    if (matches and "legacy_migration" in matches[0][1]) or any(
        directory.glob("*.migration-done")
    ):
        from logbook_cli.legacy_migration import assert_authority

        assert_authority(root, directory, relative, matches[0] if matches else None)
    if matches:
        path, value = matches[0]
        from logbook_cli import legacy_run
        from logbook_cli.services.dependency_transaction import present

        if not recovering_dependencies and present(path):
            raise LbError("unfinished dependency transaction; use log recover on its Logbook", EXIT_REFUSED)
        migration = value.get("legacy_migration")
        conflict = "old document layout conflicts with unified run"
        documents = [directory.parent / p for p in value["identity"]["document_paths"]]
        retained = set()
        if migration:
            from logbook_cli.legacy_migration import verify_legacy_sources

            verify_legacy_sources(root, directory, migration, value["execution"])
            retained = {root / source for source in migration["sources"]}
        legacy_run.disjoint_sidecars(root, directory, documents, conflict, retained=retained)
        return path, value
    if undecodable_markdown:
        # Without a verified Run, an undecodable file could still hold authority.
        raise LbError(f"invalid state {undecodable_markdown[0].name}", EXIT_REFUSED)
    if required:
        raise LbError("initialization_required: run log init-state", EXIT_REFUSED)
    return None, None


@contextmanager
def writer(root, log, dry_run=False):
    if dry_run:
        yield
        return
    import fcntl

    from logbook_cli.storage import WriterBusy

    directory = state.directory(log, root)
    directory.mkdir(exist_ok=True)
    with state.open_directory(root, directory) as directory_fd:
        fd = os.open(
            ".lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK,
            0o600, dir_fd=directory_fd,
        )
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise LbError("unsafe project writer lock", EXIT_REFUSED)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise WriterBusy("writer_busy: another run writer is active") from exc
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


def publish_run(root, path, value, *, requires_dependencies=True):
    """Publish an actual Run mutation under its writer lock, staging cutover if eligible."""
    from logbook_cli.repository import markdown_document
    from logbook_cli.services import dependencies
    from logbook_cli.task_identity import bindings

    if "dependency_source" not in value:
        try:
            log = path.parent.parent / value["identity"]["log_path"]
            doc = markdown_document(state.read_regular(root, log), log, root)
            if not any(stage.unknown_task_lines for stage in doc.stages) and len(
                bindings(doc)
            ) == sum(len(stage.tasks) for stage in doc.stages):
                dependencies.stage_cutover(doc, path, value)
        except LbError:
            if requires_dependencies:
                raise
    return publish(path, value)


@contextmanager
def initialization_writer(root, log, documents, dry_run):
    from logbook_cli import legacy_run
    from logbook_cli.storage import WriterBusy, legacy_document_lock

    directory = state.directory(log, root)
    with legacy_document_lock(
        root, directory.parent, shared=dry_run,
        busy="writer_busy: another legacy writer is active",
    ):
        sections = legacy_run.disjoint_sidecars(
            root, directory, documents, "old layout conflict; no migration", initializing=True
        )
        legacy_run.require_disjoint_observations(root, directory, sections)
        if dry_run and legacy_run.lock_busy(root, directory / ".lock"):
            raise WriterBusy("writer_busy: another run writer is active")
        with writer(root, log, dry_run):
            yield directory


def initialize(root, log, name, documents, dry_run=False):
    from logbook_cli import execution
    from logbook_cli.document import safe_path

    validate_name(name)
    base = state.project(log, root)
    paths = sorted(
        {
            state.section(log, root),
            *[str(safe_path(root, p).relative_to(base)) for p in documents],
        }
    )
    selected = [safe_path(base, relative) for relative in paths]
    with initialization_writer(root, log, selected, dry_run) as directory:
        target = directory / (name + ".json")
        found, _ = locate(root, log)
        if found is not None and found != target:
            raise LbError("document already associated with another run", EXIT_REFUSED)
        if execution.find_legacy(root, log)[0] is not None:
            raise LbError(
                "old execution layout conflict; use log migrate-state --dry-run",
                EXIT_REFUSED,
            )
        if target.exists():
            prior = read(target, root)
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
            if base / relative != log and execution.find_legacy(
                root, base / relative, include_thinking=True
            )[0] is not None:
                raise LbError(
                    "associated document is bound to an old execution layout",
                    EXIT_REFUSED,
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


def section_content(value, section):
    data = {"identity": value["identity"], section: value[section]}
    if section == "execution" and "preflight" in value:
        data["preflight"] = value["preflight"]
    return encode(data)


def section_token(value, section):
    return hashlib.sha256(section_content(value, section)).hexdigest()
