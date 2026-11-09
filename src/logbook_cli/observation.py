"""Observation state scope and read projection, separate from document state."""

import fcntl
import hashlib
import json
import os
import stat
import uuid
from contextlib import contextmanager

from logbook_cli import state
from logbook_cli.document import EXIT_PATH, EXIT_REFUSED, LbError


def scope(doc):
    identity = doc.metadata.get("document", {}).get("identity", {}).get("uuid")
    name = identity or str(doc.path.relative_to(doc.root))
    path = state.directory(doc.path, doc.root) / "observations" / (name + ".json")
    if path.parent.is_symlink() or path.is_symlink():
        raise LbError(
            "invalid_transition: observation paths cannot be symlinks", EXIT_REFUSED
        )
    return path


def validate(value):
    from logbook_cli.services.agent_wait import validate as validate_targets
    from logbook_cli.wait_state import initial

    if not isinstance(value, dict) or value.get("format") != "lb-observation":
        raise ValueError("unsupported observation format")
    if (
        not isinstance(value.get("id"), str)
        or len(value["id"]) != 32
        or uuid.UUID(hex=value["id"]).hex != value["id"]
    ):
        raise ValueError("invalid observation identity")
    targets, _, _, _ = validate_targets({"targets": value.get("targets")})
    contexts = value.get("contexts")
    if not isinstance(contexts, list) or len(contexts) != len(targets):
        raise ValueError("invalid observation cursors")
    for cursor, target in zip(contexts, targets):
        if (
            not isinstance(cursor, dict)
            or set(cursor) != set(initial(target))
            or cursor.get("binding") != target["binding"]
        ):
            raise ValueError("invalid observation cursor binding")
    if not isinstance(value.get("events"), list) or not isinstance(
        value.get("answers"), list
    ):
        raise ValueError("invalid event/answer collections")


@contextmanager
def parent_directory(path, root, create=False):
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in path.parent.relative_to(root).parts:
            try:
                child = os.open(
                    part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd
                )
            except FileNotFoundError:
                if not create:
                    yield None
                    return
                os.mkdir(part, 0o700, dir_fd=fd)
                os.fsync(fd)
                child = os.open(
                    part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd
                )
            except OSError as exc:
                raise LbError(
                    "invalid_transition: unsafe observation directory", EXIT_REFUSED
                ) from exc
            os.close(fd)
            fd = child
        yield fd
    finally:
        os.close(fd)


def read_bytes(doc):
    path = scope(doc)
    with parent_directory(path, doc.root) as directory:
        if directory is None:
            return None
        try:
            fd = os.open(
                path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory
            )
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise LbError(
                "invalid_transition: unsafe observation file", EXIT_REFUSED
            ) from exc
        with os.fdopen(fd, "rb") as handle:
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                raise LbError(
                    "invalid_transition: observation must be regular", EXIT_REFUSED
                )
            return handle.read(8 * 1024 * 1024 + 1)


def _snapshot(doc):
    path = scope(doc)
    data = read_bytes(doc)
    try:
        if data is not None and len(data) > 8 * 1024 * 1024:
            raise ValueError("oversized observation")
        value = (
            json.loads(data, object_pairs_hook=state.unique_object)
            if data is not None
            else None
        )
        if data is not None:
            validate(value)
    except (ValueError, TypeError) as exc:
        raise LbError("invalid_transition: " + str(exc), EXIT_REFUSED) from exc
    return value, version_token(path, data), data


def version_token(path, data):
    framed = b"lb-observation\0" + str(path).encode() + b"\0"
    framed += b"absent" if data is None else b"present:" + data
    return hashlib.sha256(framed).hexdigest()


def read(doc):
    value, token, _ = _snapshot(doc)
    return value, token


def configure(doc, targets, contexts, expected, dry_run):
    from contextlib import ExitStack

    with listener_lock(doc), ExitStack() as actions:
        current, observed_token = read(doc)
        if expected != observed_token:
            raise LbError("version_conflict: reread observation context", EXIT_REFUSED)
        affected = (
            []
            if current is None
            else [
                item["binding"]
                for item in current["targets"]
                if item["binding"] not in [row["binding"] for row in targets]
            ]
        )
        if not dry_run:
            for binding in sorted(affected, key=encode):
                actions.enter_context(action_lock(doc, binding))
        fd = os.open(doc.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise LbError(
                    "writer_busy: another state writer is active", EXIT_REFUSED
                ) from exc
            return _configure(doc, targets, contexts, expected, dry_run)
        finally:
            os.close(fd)


def _configure(doc, targets, contexts, expected, dry_run):
    if not doc.metadata.get("document", {}).get("identity", {}).get("uuid"):
        raise LbError("identity_missing: migrate the document explicitly", EXIT_REFUSED)
    value, current, before = _snapshot(doc)
    if expected != current:
        raise LbError("version_conflict: reread observation context", EXIT_REFUSED)
    path = scope(doc)
    value = value or {
        "format": "lb-observation",
        "id": uuid.uuid4().hex,
        "events": [],
        "answers": [],
    }
    bindings = [item["binding"] for item in targets]
    for answer in value["answers"]:
        if (
            answer["status"] in {"unknown", "submitted"}
            and answer.get("binding") not in bindings
        ):
            raise LbError(
                "delivery_unresolved: cannot retire binding with pending Answer",
                EXIT_REFUSED,
            )
    import copy

    known = copy.deepcopy(value.get("retired", {}))
    active = {}
    for item, cursor in zip(value.get("targets", []), value.get("contexts", [])):
        key = hashlib.sha256(encode(item["binding"])).hexdigest()
        known[key] = {"target": item, "context": cursor}
        active[key] = known[key]
    selected = {}
    for item, cursor in zip(targets, contexts):
        key = hashlib.sha256(encode(item["binding"])).hexdigest()
        if key in known:
            if item.get("baseline", {}) != known[key]["target"].get("baseline", {}):
                raise LbError(
                    "invalid_transition: known binding baseline cannot reset",
                    EXIT_REFUSED,
                )
            if key not in active and known[key]["context"]["reported"] in {
                "identity_changed",
                "exited",
            }:
                raise LbError(
                    "invalid_transition: terminal binding requires a new identity",
                    EXIT_REFUSED,
                )
            selected[key] = known[key]
        else:
            selected[key] = {"target": item, "context": cursor}
    if set(selected) != set(active):
        value.update(
            targets=[row["target"] for row in selected.values()],
            contexts=[row["context"] for row in selected.values()],
            retired={key: row for key, row in known.items() if key not in selected},
            target_revision=value.get("target_revision", 0) + 1,
        )
    admit(value)
    data = encode(value)
    if not dry_run and data != before:
        _publish(doc, data, before, create=True)
    return {
        "observation": value,
        "version_token": current if dry_run else version_token(path, data),
        "dry_run": dry_run,
    }


STATE_LIMIT = 8 * 1024 * 1024
EVENT_LIMIT = 4096
ANSWER_LIMIT = 4096
HISTORY_LIMIT = 8192
RECORD_LIMIT = 16 * 1024
LIFECYCLE_RESERVE = 64 * 1024


def encode(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n").encode()


def admit(value, *, new_work=True):
    """Account for actual bytes and every outstanding completion before a write.

    Reservations are derived from protected durable state, never a caller quota.
    A terminal operation may consume its own reservation without reserving a new
    observation batch. Unresolved objects always retain their completion budget.
    """
    events, answers = value["events"], value["answers"]
    batch = len(value["targets"]) if new_work else 0
    pending = sum(event.get("handling") != "resolved" for event in events)
    steps = sum(
        {"unknown": 2, "submitted": 1, "confirmed": 0, "not_submitted": 0}.get(
            answer.get("status"), 2
        )
        for answer in answers
    )
    history = sum(len(row.get("history", [])) for row in [*events, *answers])
    reserved_history = pending + steps + batch
    # One batch event plus its conclusion/history; one conclusion and one history
    # record per pending Event; receipt plus history per remaining Answer step.
    reserved_bytes = LIFECYCLE_RESERVE + RECORD_LIMIT * (
        3 * batch + 2 * pending + 2 * steps
    )
    if (
        len(events) + batch > EVENT_LIMIT
        or len(answers) > ANSWER_LIMIT
        or history + reserved_history > HISTORY_LIMIT
        or len(encode(value)) + reserved_bytes > STATE_LIMIT
    ):
        raise LbError(
            "capacity_exceeded: completion space must remain available", EXIT_REFUSED
        )
    for row in [*events, *answers]:
        _evidence_bounds(row)
        for entry in row.get("history", []):
            if len(encode(entry)) > RECORD_LIMIT:
                raise LbError(
                    "capacity_exceeded: transition record exceeds 16 KiB", EXIT_REFUSED
                )
        for field in ("conclusion", "receipt", "confirmation"):
            if field in row and len(encode(row[field])) > RECORD_LIMIT:
                raise LbError(
                    "capacity_exceeded: completion record exceeds 16 KiB", EXIT_REFUSED
                )


def _evidence_bounds(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if (
                key in {"summary", "reason"}
                and isinstance(item, str)
                and len(item.encode()) > 4096
            ):
                raise LbError("capacity_exceeded: summary exceeds 4 KiB", EXIT_REFUSED)
            if key in {"evidence", "references"} and isinstance(item, list):
                if len(item) > 4 or any(
                    isinstance(ref, str) and len(ref.encode()) > 2048 for ref in item
                ):
                    raise LbError(
                        "capacity_exceeded: at most four 2 KiB references", EXIT_REFUSED
                    )
            _evidence_bounds(item)
    elif isinstance(value, list):
        for item in value:
            _evidence_bounds(item)


def _publish(doc, data, before, *, create=False):
    from logbook_cli.storage import replace_bytes_at

    path = scope(doc)
    try:
        with parent_directory(path, doc.root, create=create) as directory:
            replace_bytes_at(directory, path.name, data, before)
    except OSError as exc:
        raise LbError(
            "persistence_failed: reread actual Observation state before recovery",
            EXIT_PATH,
        ) from exc


def _lock_file(directory, name, *, create):
    if directory is None:
        raise LbError(
            "invalid_transition: coordination directory disappeared", EXIT_REFUSED
        )
    flags = os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK
    if create:
        try:
            return os.open(
                name, flags | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=directory
            )
        except FileExistsError:
            pass
    return os.open(name, flags, dir_fd=directory)


@contextmanager
def listener_lock(doc, *, create=False):
    path = scope(doc).with_suffix(".listener")
    with parent_directory(path, doc.root) as directory:
        if directory is None:
            yield
            return
        try:
            fd = _lock_file(directory, path.name, create=create)
        except FileNotFoundError:
            yield
            return
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise LbError("listener_busy: unsafe listener lock", EXIT_REFUSED)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise LbError(
                    "listener_busy: observation already has a listener", EXIT_REFUSED
                ) from exc
            yield
        finally:
            os.close(fd)


def _change(doc, expected, mutate, *, new_work=False, dry_run=False):
    """Apply an owned delta to fresh protected state; never save a stale snapshot."""
    fd = os.open(doc.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise LbError(
                "writer_busy: another state writer is active", EXIT_REFUSED
            ) from exc
        value, token, before = _snapshot(doc)
        if value is None:
            raise LbError(
                "observation_not_configured: configure before wait", EXIT_REFUSED
            )
        if expected is not None and token != expected:
            raise LbError("version_conflict: reread observation context", EXIT_REFUSED)
        canonical_before = encode(value)
        mutate(value)
        data = encode(value)
        if data == canonical_before:
            return value, token
        admit(value, new_work=new_work)
        if not dry_run and data != before:
            _publish(doc, data, before)
        return value, token if dry_run else version_token(scope(doc), data)
    finally:
        os.close(fd)


@contextmanager
def action_lock(doc, binding):
    digest = hashlib.sha256(encode(binding)).hexdigest()
    path = scope(doc).with_suffix(".action-" + digest)
    with parent_directory(path, doc.root) as directory:
        fd = _lock_file(directory, path.name, create=True)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise LbError("invalid_transition: unsafe action lock", EXIT_REFUSED)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise LbError(
                    "delivery_unresolved: binding action is active", EXIT_REFUSED
                ) from exc
            yield
        finally:
            os.close(fd)


def event_transition(value, event_id, action_id, action, payload):
    import copy
    from datetime import datetime, timezone

    event = next((row for row in value["events"] if row["id"] == event_id), None)
    if event is None:
        raise LbError("invalid_transition: unknown Event", EXIT_REFUSED)
    digest = hashlib.sha256(encode({"action": action, "payload": payload})).hexdigest()
    previous = next((row for row in event["history"] if row["id"] == action_id), None)
    if previous is not None:
        if previous["digest"] != digest:
            raise LbError(
                "invalid_transition: action ID content conflict", EXIT_REFUSED
            )
        return copy.deepcopy(previous["result"])
    if event["handling"] == "resolved":
        raise LbError("invalid_transition: Event is already resolved", EXIT_REFUSED)
    if action == "resolve":
        if event["observation"]["kind"] == "needs_input" and "obsolete" not in payload:
            raise LbError(
                "invalid_transition: answering requires matched Answer confirmation",
                EXIT_REFUSED,
            )
        binding = event["observation"]["binding"]
        if any(
            answer.get("status") in {"unknown", "submitted"}
            and (answer.get("event_id") == event_id or answer.get("binding") == binding)
            for answer in value["answers"]
        ):
            raise LbError(
                "delivery_unresolved: reconcile pending Answer first", EXIT_REFUSED
            )
    conclusion = {
        "action": action,
        "payload": copy.deepcopy(payload),
        "source": "caller",
    }
    result = {
        "event_id": event_id,
        "handling": "deferred" if action == "defer" else "resolved",
        "conclusion": conclusion,
    }
    event.update(handling=result["handling"], conclusion=conclusion)
    event["history"].append(
        {
            "id": action_id,
            "digest": digest,
            "action": action,
            "at": datetime.now(timezone.utc).isoformat(),
            "result": copy.deepcopy(result),
        }
    )
    return result


def answer_intent(
    value, event_id, operation_id, mode, request_digest, correlation, *, create
):
    import copy

    previous = next(
        (row for row in value["answers"] if row["id"] == operation_id), None
    )
    if previous is not None:
        if (
            previous["request_digest"] != request_digest
            or previous["mode"] != mode
            or previous["event_id"] != event_id
        ):
            raise LbError(
                "invalid_transition: operation ID content/mode conflict", EXIT_REFUSED
            )
        return copy.deepcopy(previous)
    event = next((row for row in value["events"] if row["id"] == event_id), None)
    if (
        event is None
        or event["handling"] == "resolved"
        or event["observation"]["kind"] != "needs_input"
    ):
        raise LbError(
            "invalid_transition: Answer requires an unresolved question", EXIT_REFUSED
        )
    binding = event["observation"]["binding"]
    if any(
        row.get("binding") == binding and row["status"] in {"unknown", "submitted"}
        for row in value["answers"]
    ):
        raise LbError(
            "delivery_unresolved: reconcile existing attempt before retry", EXIT_REFUSED
        )
    if not create:
        return None
    answer = {
        "id": operation_id,
        "mode": mode,
        "event_id": event_id,
        "binding": copy.deepcopy(binding),
        "status": "unknown",
        "request_digest": request_digest,
        "history": [],
        **correlation,
    }
    value["answers"].append(answer)
    return copy.deepcopy(answer)


def answer_receipt(value, operation_id, receipt, source):
    import copy

    answer = next(row for row in value["answers"] if row["id"] == operation_id)
    allowed = {
        "receipt_id",
        "outcome",
        "question_id",
        "answer_digest",
        "evidence",
        "non_submission",
        "executor_terminated",
    }
    if (
        not isinstance(receipt, dict)
        or set(receipt) - allowed
        or not {"receipt_id", "outcome", "answer_digest", "evidence"}.issubset(receipt)
        or not isinstance(receipt["receipt_id"], str)
        or not 1 <= len(receipt["receipt_id"]) <= 512
        or receipt["outcome"] not in {"submitted", "confirmed", "not_submitted"}
        or receipt["answer_digest"] != answer["answer_digest"]
        or receipt.get("question_id") != answer.get("question_id")
        or not isinstance(receipt["evidence"], list)
        or not receipt["evidence"]
        or any(
            not isinstance(ref, str) or not ref.strip() for ref in receipt["evidence"]
        )
    ):
        raise LbError(
            "invalid_transition: receipt does not match question/answer", EXIT_REFUSED
        )
    _evidence_bounds(receipt)
    if len(encode(receipt)) > RECORD_LIMIT:
        raise LbError("capacity_exceeded: receipt exceeds 16 KiB", EXIT_REFUSED)
    digest = hashlib.sha256(encode({"receipt": receipt, "source": source})).hexdigest()
    previous = next(
        (row for row in answer["history"] if row["id"] == receipt["receipt_id"]), None
    )
    if previous is not None:
        if previous["digest"] != digest:
            raise LbError("invalid_transition: contradictory receipt", EXIT_REFUSED)
        return copy.deepcopy(answer)
    outcome = receipt["outcome"]
    if answer["status"] in {"confirmed", "not_submitted"}:
        raise LbError("invalid_transition: terminal Answer cannot change", EXIT_REFUSED)
    if outcome == "not_submitted" and (
        not isinstance(receipt.get("non_submission"), str)
        or not receipt["non_submission"].strip()
        or (
            answer["mode"] == "external"
            and receipt.get("executor_terminated") is not True
        )
    ):
        raise LbError(
            "delivery_unresolved: affirmative non-submission and executor termination required",
            EXIT_REFUSED,
        )
    answer["status"] = outcome
    answer["history"].append(
        {
            "id": receipt["receipt_id"],
            "digest": digest,
            "receipt": copy.deepcopy(receipt),
            "source": source,
        }
    )
    if outcome == "confirmed":
        event = next(row for row in value["events"] if row["id"] == answer["event_id"])
        event["handling"] = "resolved"
        event["conclusion"] = {
            "source": source,
            "answer_id": operation_id,
            "receipt_id": receipt["receipt_id"],
            "evidence": receipt["evidence"],
        }
    return copy.deepcopy(answer)
