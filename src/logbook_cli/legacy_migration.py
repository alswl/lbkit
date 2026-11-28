"""Atomically switch authority between an intact legacy snapshot and a unified run."""

import base64
import fcntl
import os
import re
import stat
from contextlib import contextmanager
from pathlib import Path

from logbook_cli import legacy_conversion, legacy_run, state, unified
from logbook_cli.document import EXIT_PATH, EXIT_REFUSED, LbError, root_path
from logbook_cli.services.common import Result
from logbook_cli.storage import legacy_document_lock, replace_bytes_at

ARCHIVE = "lb-legacy-migration-backup-v1"
ROLLED_BACK = "lb-legacy-migration-rolled-back-v1"
COMMITTED = "lb-legacy-migration-committed-v1"
CHECKSUM = re.compile(r"[0-9a-f]{64}")


def refuse(message):
    raise LbError(message, EXIT_REFUSED)


def validate_manifest(value):
    if (
        not isinstance(value, dict)
        or set(value) - {"history_sha256", "send_attempt_mapping"}
        != {
            "plan_token",
            "backup_sha256",
            "sources",
            "document_uuids",
            "execution_name",
            "send_task_mapping",
        }
        or any(
            not isinstance(value[key], str) or not CHECKSUM.fullmatch(value[key])
            for key in ("plan_token", "backup_sha256")
        )
        or (
            "history_sha256" in value
            and (
                not isinstance(value["history_sha256"], str)
                or not CHECKSUM.fullmatch(value["history_sha256"])
            )
        )
        or not isinstance(value["sources"], dict)
        or not isinstance(value["document_uuids"], dict)
        or not isinstance(value["send_task_mapping"], dict)
        or any(
            not isinstance(key, str) or not isinstance(task, str) or not task
            for key, task in value["send_task_mapping"].items()
        )
        or (
            value["execution_name"] is not None
            and (
                not isinstance(value["execution_name"], str)
                or Path(value["execution_name"]).name != value["execution_name"]
            )
        )
        or any(
            not isinstance(checksum, str) or not CHECKSUM.fullmatch(checksum)
            for checksum in value["sources"].values()
        )
    ):
        raise ValueError("invalid legacy migration manifest")
    attempts = value.get("send_attempt_mapping", {})
    if (
        not isinstance(attempts, dict)
        or set(attempts) - set(value["send_task_mapping"])
        or any(
            not isinstance(ids, list)
            or not ids
            or any(not isinstance(key, str) or not key.strip() for key in ids)
            or len(set(ids)) != len(ids)
            for ids in attempts.values()
        )
    ):
        raise ValueError("invalid legacy Attempt mapping")


def verify_legacy_sources(root, directory, manifest, execution):
    old_execution = None
    for relative, checksum in manifest["sources"].items():
        path = root / relative
        if (
            Path(relative).as_posix() != relative
            or not path.is_relative_to(directory)
            or ".." in path.parts
            or path.suffix != ".json"
            or path.parent not in (directory, directory / "observations")
        ):
            refuse("invalid retained legacy source location")
        try:
            data = state.read_regular(root, path)
        except OSError as exc:
            raise LbError(
                f"retained legacy source unavailable: {relative}", EXIT_REFUSED
            ) from exc
        if legacy_conversion.checksum(data) != checksum:
            refuse(f"retained legacy source changed: {relative}")

        if path == directory / f"{manifest['execution_name']}.json":
            old_execution = load_json(data)
    if old_execution is None:
        if manifest["execution_name"] is not None or manifest["send_task_mapping"]:
            refuse("migration execution source is unavailable")
        return
    original = {op["id"]: op for op in old_execution["operations"]}
    mapping = manifest["send_task_mapping"]
    runtime_facts = execution["facts"]
    if (
        set(original) != set(mapping)
        or runtime_facts[: len(old_execution["facts"])] != old_execution["facts"]
    ):
        refuse("retained legacy execution facts or mapping changed")
    for key, old in original.items():
        current = execution["operations"].get(key)
        expected = dict(old, legacy_task_id=mapping[key])
        attempts = manifest.get("send_attempt_mapping", {}).get(key)
        if attempts:
            expected["legacy_attempt_ids"] = attempts
        if current == expected:
            continue
        if current is not None and old["outcome"] == "unknown":
            evidence = [
                fact
                for fact in runtime_facts[len(old_execution["facts"]) :]
                if fact.get("kind") == "transport-resolution"
                and fact.get("operation_id") == key
            ]
            if len(evidence) == 1 and evidence[0]["outcome"] in {
                "submitted",
                "not_submitted",
            }:
                fact = evidence[0]
                expected.update(
                    outcome=fact["outcome"],
                    receipt={"evidence_ref": fact["source"]["ref"]}
                    if fact["outcome"] == "submitted"
                    else None,
                    provenance="caller_reported_runtime_observation",
                )
                if current == expected:
                    continue
        refuse(f"retained legacy operation changed without reconciliation: {key}")


def scope(root, log, name, documents):
    base = root_path(root)
    log_path = legacy_run.document(base, log)
    unified.validate_name(name)
    project = state.project(log_path, base)
    directory = state.directory(log_path, base)
    request = {
        "log": log_path.relative_to(base).as_posix(),
        "documents": sorted(
            {
                legacy_run.document(base, path, "--document").relative_to(base).as_posix()
                for path in documents
            }
        ),
        "target": (directory / (name + ".json")).relative_to(base).as_posix(),
    }
    return base, project, directory, request


def initial_candidate(archive):
    initial = archive["initial"]
    manifest = {
        "plan_token": archive["plan_token"],
        "backup_sha256": unified.digest(archive),
        "sources": archive["legacy_sources"],
        "document_uuids": archive["document_uuids"],
        "execution_name": archive["execution_name"],
        "send_task_mapping": {
            key: op["legacy_task_id"]
            for key, op in initial["execution"]["operations"].items()
        },
    }
    if "legacy_history" in initial:
        manifest["history_sha256"] = unified.digest(initial["legacy_history"])
    attempts = {
        key: op["legacy_attempt_ids"]
        for key, op in initial["execution"]["operations"].items()
        if "legacy_attempt_ids" in op
    }
    if attempts:
        manifest["send_attempt_mapping"] = attempts
    return dict(initial, legacy_migration=manifest)


def prepare(base, project, name, request, *, writers_locked=False):
    try:
        result = legacy_run.preview(
            str(base),
            request["log"],
            name,
            request["documents"],
            writers_locked=writers_locked,
        )
        inventory = result.value
        inventory["message"] = "Resolve the reported conflicts before applying."
        if result.code:
            return result, None
        snapshot = legacy_conversion.source_snapshot(base, project, inventory)
        initial = legacy_conversion.candidate(base, project, inventory, snapshot)
    except (ValueError, KeyError, TypeError) as exc:
        raise LbError(
            "invalid or inconsistent legacy source data", EXIT_REFUSED
        ) from exc
    except LbError as exc:
        if "inventory" not in locals():
            raise
        inventory["conflicts"].append(
            {"code": "conversion_refused", "message": exc.message}
        )
        return Result(inventory, EXIT_REFUSED), None

    sources = inventory["sources"]
    checksums = {
        key: legacy_conversion.checksum(data) for key, data in snapshot.items()
    }
    source_paths = {row["path"] for row in sources["sidecars"]}
    source_paths.update(
        sources[k]["path"] for k in ("execution", "monitoring") if sources[k]
    )
    archive = {
        "format": ARCHIVE,
        "request": request,
        "before": {
            key: base64.b64encode(data).decode() for key, data in snapshot.items()
        },
        "sha256": checksums,
        "legacy_sources": {key: checksums[key] for key in sorted(source_paths)},
        "document_uuids": inventory["identity"]["document_uuids"],
        "execution_name": sources["execution"]["name"]
        if sources["execution"]
        else None,
        "initial": initial,
    }
    archive["plan_token"] = unified.digest(archive)
    proposed = initial_candidate(archive)
    inventory.update(
        plan_token=archive["plan_token"],
        apply_available=True,
        message="Apply requires an explicit --apply and the current plan token.",
        source_sha256=checksums,
        target_sha256=unified.digest(proposed),
        send_task_mapping=proposed["legacy_migration"]["send_task_mapping"],
    )
    if "send_attempt_mapping" in proposed["legacy_migration"]:
        inventory["send_attempt_mapping"] = proposed["legacy_migration"][
            "send_attempt_mapping"
        ]
    return result, archive


def read_at(fd, name):
    try:
        source = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
    except FileNotFoundError:
        return None
    with os.fdopen(source, "rb") as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            refuse(f"unsafe migration file: {name}")
        return handle.read()


def load_json(data):
    if data is None:
        return None
    try:
        value = state.decode_json(data)
    except (ValueError, TypeError) as exc:
        raise LbError("invalid migration state", EXIT_REFUSED) from exc
    if not isinstance(value, dict):
        refuse("invalid migration state")
    return value


def checked_archive(before, request):
    archive = load_json(before)
    if archive is None:
        return None
    if archive.get("format") != ARCHIVE or archive.get("request") != request:
        refuse("migration backup belongs to another request")
    if set(archive) != {
        "format",
        "request",
        "before",
        "sha256",
        "legacy_sources",
        "document_uuids",
        "execution_name",
        "initial",
        "plan_token",
    }:
        refuse("invalid migration backup")
    token = archive["plan_token"]
    if (
        unified.encode(archive) != before
        or unified.digest(
            {key: value for key, value in archive.items() if key != "plan_token"}
        )
        != token
    ):
        refuse("migration backup checksum differs")
    try:
        original = {
            name: legacy_conversion.checksum(base64.b64decode(data, validate=True))
            for name, data in archive["before"].items()
        }
        if original != archive["sha256"] or any(
            original[key] != value for key, value in archive["legacy_sources"].items()
        ):
            refuse("migration backup source checksum differs")
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        raise LbError("invalid migration backup sources", EXIT_REFUSED) from exc
    return archive


def verify_snapshot(base, archive):
    for name, digest in archive["sha256"].items():
        try:
            data = state.read_regular(base, base / name)
        except OSError as exc:
            raise LbError(
                f"migration source unavailable: {name}", EXIT_REFUSED
            ) from exc
        if legacy_conversion.checksum(data) != digest:
            refuse(f"migration source changed: {name}")


def lock(fd, description):
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        refuse(f"migration_busy: {description}")


@contextmanager
def transaction(base, directory, dry_run):
    if dry_run:
        with state.open_directory(base, directory) as fd:
            yield fd
        return
    with (
        legacy_document_lock(base, directory.parent, busy="migration_busy: legacy document writer"),
        state.open_directory(base, directory) as fd,
    ):
        project_lock = os.open(
            ".lock",
            os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK,
            0o600,
            dir_fd=fd,
        )
        try:
            if not stat.S_ISREG(os.fstat(project_lock).st_mode):
                refuse("unsafe migration writer lock")
            lock(project_lock, "project writer")
            yield fd
        finally:
            os.close(project_lock)


def monitor_names(base, directory, target, archive):
    files = [target]
    observation_root = directory / "observations"
    for relative in archive["legacy_sources"]:
        path = base / relative
        if path.parent == observation_root:
            files.append(path)
    return [
        lock_path
        for path in files
        for lock_path in (
            path.with_suffix(".listener"),
            *sorted(path.parent.glob(f"{path.stem}.action-*")),
        )
    ]


def verify_idle(base, directory, target, archive):
    for path in monitor_names(base, directory, target, archive):
        if legacy_run.lock_busy(base, path):
            refuse(f"migration_busy: {path.relative_to(base)}")
    locations = {base / relative for relative in archive["sha256"]}
    if any(
        legacy_run.is_present(base, state.journal_for(path, base))
        for path in locations
        if path.suffix == ".md"
        or (path.parent == directory and not path.name.endswith(".md.json"))
    ):
        refuse("migration_busy: legacy recovery transaction is present")


def receipt(archive, *, changed, rolled_back=False, dry_run=False):
    return {
        "dry_run": dry_run,
        "changed": changed,
        "status": "rolled_back" if rolled_back else "applied",
        "plan_token": archive["plan_token"],
        "target": archive["request"]["target"],
        "target_sha256": unified.digest(initial_candidate(archive)),
        "source_sha256": archive["sha256"],
        "backup_sha256": unified.digest(archive),
    }


def done_name(target):
    return target.stem + ".migration-done"


def publication(archive):
    initial = initial_candidate(archive)
    return {
        "format": COMMITTED,
        "document_paths": initial["identity"]["document_paths"],
        "manifest": initial["legacy_migration"],
        "rollback_token": rollback_token(archive),
    }


def assert_authority(root, directory, relative, selected):
    committed = False
    for marker in sorted(directory.glob("*.migration-done")):
        source = load_json(state.read_regular(root, marker))
        try:
            if (
                source.get("format") != COMMITTED
                or not isinstance(source["document_paths"], list)
                or any(
                    not isinstance(name, str)
                    or Path(name).is_absolute()
                    or ".." in Path(name).parts
                    for name in source["document_paths"]
                )
                or not isinstance(source["rollback_token"], str)
                or not CHECKSUM.fullmatch(source["rollback_token"])
            ):
                raise ValueError("invalid migration publication receipt")
            validate_manifest(source["manifest"])
        except (AttributeError, KeyError, ValueError) as exc:
            raise LbError(
                f"invalid migration publication receipt: {marker.name}", EXIT_REFUSED
            ) from exc
        if relative not in source["document_paths"]:
            continue
        target = marker.with_suffix(".json")
        if selected and selected[0] == target:
            if selected[1].get("legacy_migration") != source["manifest"]:
                refuse("active migration differs from its publication receipt")
            committed = True
            continue
        try:
            current = load_json(state.read_regular(root, target))
        except FileNotFoundError:
            refuse("migration destination is missing; legacy authority remains fenced")
        if current != {
            "format": ROLLED_BACK,
            "plan_token": source["manifest"]["plan_token"],
            "rollback_token": source["rollback_token"],
        }:
            refuse("migration destination conflicts with its publication receipt")
    if selected and "legacy_migration" in selected[1] and not committed:
        refuse("migration publication is incomplete; repeat the reviewed apply command")


def finish_publication(fd, target, archive):
    name = done_name(target)
    expected = unified.encode(publication(archive))
    persisted = read_at(fd, name)
    if persisted is None:
        replace_bytes_at(fd, name, expected, None)
        return True
    if persisted != expected:
        refuse("migration publication receipt differs")
    os.fsync(fd)
    return False


def rollback_token(archive):
    return unified.digest(
        [
            "rollback-v1",
            archive["plan_token"],
            unified.digest(initial_candidate(archive)),
        ]
    )


def check_token(expected, current):
    if expected != current:
        refuse("migration plan token differs; obtain a fresh dry-run")


def inspect_rollback_writers(base, directory):
    for location in dict.fromkeys((base, directory.parent)):
        with state.open_directory(base, location) as fd:
            if legacy_run.exclusive_lock_held(fd):
                refuse("migration_busy: legacy document writer")
    if legacy_run.lock_busy(base, directory / ".lock"):
        refuse("migration_busy: project writer")


def rollback(base, directory, fd, target, archive, current, envelope, dry_run, token):
    if archive is None or envelope is None:
        refuse("no completed migration is available to roll back")
    if read_at(fd, done_name(target)) != unified.encode(publication(archive)):
        refuse("migration publication is incomplete; repeat the reviewed apply command")
    expected = rollback_token(archive)
    marker = {
        "format": ROLLED_BACK,
        "plan_token": archive["plan_token"],
        "rollback_token": expected,
    }
    complete = envelope == marker
    if not complete and current != unified.encode(initial_candidate(archive)):
        refuse("unified state changed since cutover; automatic rollback is unsafe")
    if not complete:
        verify_snapshot(base, archive)
    if dry_run:
        inspect_rollback_writers(base, directory)
    verify_idle(base, directory, target, archive)
    if not dry_run:
        check_token(token, expected)
        if not complete:
            replace_bytes_at(fd, target.name, unified.encode(marker), current)
        else:
            os.fsync(fd)
    value = receipt(
        archive,
        changed=not complete and not dry_run,
        rolled_back=complete or not dry_run,
        dry_run=dry_run,
    )
    value.update(rollback_token=expected, action="rollback")
    return Result(value)


def run(root, log, name, documents, *, dry_run, is_rollback, token):
    base, project, directory, request = scope(root, log, name, documents)
    target = base / request["target"]
    backup_name = name + ".migration-backup"
    if dry_run and not is_rollback:
        result, proposed = prepare(base, project, name, request)
        if proposed is not None:
            try:
                with state.open_directory(base, directory) as fd:
                    before = read_at(fd, backup_name)
                archive = checked_archive(before, request)
                if archive is not None and archive != proposed:
                    refuse("prepared migration backup has a different plan")
                verify_idle(base, directory, target, proposed)
            except (OSError, LbError) as exc:
                message = exc.message if isinstance(exc, LbError) else str(exc)
                inventory = result.value
                inventory["conflicts"].append(
                    {"code": "migration_refused", "message": message}
                )
                inventory.update(
                    apply_available=False,
                    message="Resolve the reported conflicts before applying.",
                )
                inventory.pop("plan_token")
                return Result(inventory, EXIT_REFUSED)
        return result
    if not dry_run and (not isinstance(token, str) or not CHECKSUM.fullmatch(token)):
        refuse("invalid migration plan token; obtain a fresh dry-run")
    if not directory.is_dir():
        refuse("no legacy sources bind this Logbook")
    try:
        with transaction(base, directory, dry_run) as fd:
            current = read_at(fd, target.name)
            envelope = load_json(current)
            before = read_at(fd, backup_name)
            archive = checked_archive(before, request)
            if is_rollback:
                return rollback(
                    base,
                    directory,
                    fd,
                    target,
                    archive,
                    current,
                    envelope,
                    dry_run,
                    token,
                )
            if envelope is not None and archive is not None:
                check_token(token, archive["plan_token"])
                if envelope.get("format") == ROLLED_BACK:
                    refuse(
                        "this migration was rolled back; choose a new destination for a new plan"
                    )
                if (
                    envelope.get("legacy_migration")
                    != initial_candidate(archive)["legacy_migration"]
                ):
                    refuse("migration destination does not match its receipt")
                verified = unified.read(target, base)
                published = read_at(fd, done_name(target))
                if published is None:
                    if current != unified.encode(initial_candidate(archive)):
                        refuse("unpublished migration state differs from the plan")
                    verify_snapshot(base, archive)
                    verify_idle(base, directory, target, archive)
                verify_legacy_sources(
                    base, directory, verified["legacy_migration"], verified["execution"]
                )
                if published is None:
                    legacy_run.disjoint_sidecar_sections(
                        base,
                        directory,
                        [project / path for path in verified["identity"]["document_paths"]],
                        legacy_run.MISPLACED_SIDECAR,
                        retained={base / path for path in archive["legacy_sources"]},
                    )
                changed = finish_publication(fd, target, archive)
                return Result(receipt(archive, changed=changed))
            if read_at(fd, done_name(target)) is not None:
                refuse(
                    "migration destination is missing; legacy authority remains fenced"
                )
            result, proposed = prepare(
                base, project, name, request, writers_locked=True
            )
            if proposed is None:
                return result
            check_token(token, proposed["plan_token"])
            if archive is not None and archive != proposed:
                refuse("prepared migration backup has a different plan")
            verify_idle(base, directory, target, proposed)
            if before is None:
                replace_bytes_at(fd, backup_name, unified.encode(proposed), None)
            verify_snapshot(base, proposed)
            replace_bytes_at(
                fd, target.name, unified.encode(initial_candidate(proposed)), None
            )
            finish_publication(fd, target, proposed)
            return Result(receipt(proposed, changed=True))
    except OSError as exc:
        raise LbError(
            f"migration persistence or access failed; recheck state and repeat the same request: {exc}",
            EXIT_PATH,
        ) from exc
