"""Typed Observation operations; runtime delivery remains in agent_wait."""

import json

from logbook_cli import observation, state
from logbook_cli.document import EXIT_REFUSED, EXIT_USAGE, LbError, safe_path
from logbook_cli.services.common import load


def _input(doc, input_file):
    with safe_path(doc.root, input_file).open("rb") as handle:
        raw = handle.read(1024 * 1024 + 1)
    try:
        if len(raw) > 1024 * 1024:
            raise ValueError("input exceeds 1 MiB")
        return json.loads(raw, object_pairs_hook=state.unique_object)
    except (ValueError, TypeError) as exc:
        raise LbError(str(exc), EXIT_USAGE) from exc


def context(root, log):
    doc = load(root, log)
    value, token = observation.read(doc)
    from logbook_cli.adapters import herdr

    events = (value or {}).get("events", [])
    unresolved = [event for event in events if event["handling"] != "resolved"]
    pending = [
        answer
        for answer in (value or {}).get("answers", [])
        if answer["status"] in {"unknown", "submitted"}
    ]
    return {
        "observation": value,
        "version_token": token,
        "unresolved_events": unresolved,
        "pending_answers": pending,
        "capabilities": {"automatic_answer": herdr.answer_capabilities()},
        "diagnostics": {
            "detected_events": len(events),
            "unresolved_events": len(unresolved),
            "pending_answers": len(pending),
            "listener_liveness": "requires exclusive lock, not saved PID/status",
        },
    }


def configure(root, log, input_file, token, dry_run):
    from logbook_cli.services.agent_wait import validate

    try:
        doc = load(root, log)
    except LbError as exc:
        if exc.message == "another document writer is active":
            raise LbError(
                "writer_busy: another state writer is active", EXIT_REFUSED
            ) from exc
        raise
    value = _input(doc, input_file)
    try:
        if not isinstance(value, dict) or set(value) != {"targets"}:
            raise ValueError("configure input must contain exactly targets")
        targets, contexts, _, _ = validate(value)
    except (ValueError, TypeError, KeyError) as exc:
        raise LbError(str(exc), EXIT_USAGE) from exc
    return observation.configure(doc, targets, contexts, token, dry_run)


def event_action(root, log, event_id, action_id, input_file, token, dry_run, action):
    from contextlib import nullcontext

    doc = load(root, log)
    payload = _input(doc, input_file)
    try:
        required = (
            {"reason", "responsible_party"}
            if action == "defer"
            else (
                {"obsolete"}
                if isinstance(payload, dict) and "obsolete" in payload
                else {"assessment"}
            )
        )
        if (
            not isinstance(payload, dict)
            or set(payload) - required - {"evidence"}
            or not required.issubset(payload)
            or any(
                not isinstance(payload[k], str) or not payload[k].strip()
                for k in required
            )
        ):
            raise ValueError("invalid Event action payload")
        references = payload.get("evidence", [])
        if (
            not isinstance(references, list)
            or any(not isinstance(ref, str) or not ref.strip() for ref in references)
            or ("obsolete" in payload and not references)
        ):
            raise ValueError(
                "obsolete requires evidence references; references must be strings"
            )
        if (
            not isinstance(action_id, str)
            or not 1 <= len(action_id) <= 512
            or any(c in action_id for c in "\n\r\x00")
        ):
            raise ValueError("invalid action ID")
    except (ValueError, TypeError, KeyError) as exc:
        raise LbError(str(exc), EXIT_USAGE) from exc
    value, current = observation.read(doc)
    if token != current:
        raise LbError("version_conflict: reread observation context", EXIT_REFUSED)
    event = next(
        (row for row in (value or {}).get("events", []) if row["id"] == event_id), None
    )
    if event is None:
        raise LbError("invalid_transition: unknown Event", EXIT_REFUSED)
    lock = (
        observation.action_lock(doc, event["observation"]["binding"])
        if action == "resolve" and not dry_run
        else nullcontext()
    )
    results = []

    def mutate(fresh):
        results.append(
            observation.event_transition(fresh, event_id, action_id, action, payload)
        )

    with lock:
        _, version = observation._change(doc, token, mutate, dry_run=dry_run)
    return {"event": results[0], "version_token": version, "dry_run": dry_run}


def _answer_context(doc, token):
    value, current = observation.read(doc)
    if token != current:
        raise LbError("version_conflict: reread observation context", EXIT_REFUSED)
    if value is None:
        raise LbError("observation_not_configured", EXIT_REFUSED)
    return value


def _digest(value):
    import hashlib

    return hashlib.sha256(observation.encode(value)).hexdigest()


def _operation_id(identity):
    if (
        not isinstance(identity, str)
        or not 1 <= len(identity) <= 512
        or any(c in identity for c in "\n\r\x00")
    ):
        raise LbError("invalid operation ID", EXIT_USAGE)


def answer_submit(root, log, event_id, operation_id, input_file, token, dry_run, mode):
    from contextlib import nullcontext

    from logbook_cli.adapters import herdr

    _operation_id(operation_id)
    doc = load(root, log)
    payload = _input(doc, input_file)
    if not isinstance(payload, dict):
        raise LbError("Answer input must be an object", EXIT_USAGE)
    if mode == "adapter":
        if set(payload) != {"question_id", "revision", "answer"} or any(
            not isinstance(payload[k], str)
            or not payload[k].strip()
            or len(payload[k].encode()) > 512
            for k in ("question_id", "revision")
        ):
            raise LbError(
                "Answer requires question_id, revision and answer", EXIT_USAGE
            )
        correlation = {
            "question_id": payload["question_id"],
            "revision": payload["revision"],
            "answer_digest": _digest(payload["answer"]),
        }
    else:
        required = {"answer_digest", "execution_owner", "evidence"}
        if (
            not required.issubset(payload)
            or set(payload) - required - {"question_id"}
            or not isinstance(payload["execution_owner"], str)
            or not payload["execution_owner"].strip()
            or not isinstance(payload["answer_digest"], str)
            or len(payload["answer_digest"]) != 64
            or not isinstance(payload["evidence"], list)
            or not payload["evidence"]
            or any(
                not isinstance(ref, str) or not ref.strip()
                for ref in payload["evidence"]
            )
        ):
            raise LbError(
                "external intent requires digest, evidence and execution_owner",
                EXIT_USAGE,
            )
        correlation = dict(payload)
    observation._evidence_bounds(correlation)
    value = _answer_context(doc, token)
    event = next((row for row in value["events"] if row["id"] == event_id), None)
    if event is None:
        raise LbError("invalid_transition: unknown Event", EXIT_REFUSED)
    binding = event["observation"]["binding"]
    request_digest = _digest(payload)
    with observation.action_lock(doc, binding) if not dry_run else nullcontext():
        prior = []

        def probe(fresh):
            prior.append(
                observation.answer_intent(
                    fresh,
                    event_id,
                    operation_id,
                    mode,
                    request_digest,
                    correlation,
                    create=False,
                )
            )

        observation._change(doc, token, probe, dry_run=True)
        if prior[0] is not None:
            return {
                "answer": prior[0],
                "version_token": observation.read(doc)[1],
                "dry_run": dry_run,
            }
        if mode == "adapter":
            native_question = event["observation"].get("question")
            if native_question is not None and (
                not isinstance(native_question, dict)
                or native_question.get("id") != payload["question_id"]
                or native_question.get("revision") != payload["revision"]
            ):
                raise LbError("identity_changed: saved Event names a different native question", EXIT_REFUSED)
            native = herdr.inspect_question(binding, payload)
            if not native.get("live_verified"):
                raise LbError(
                    "identity_missing: native binding is not verified", EXIT_REFUSED
                )
            if not native.get("confirmation_supported"):
                raise LbError(
                    "capability_unavailable: no question confirmation", EXIT_REFUSED
                )
            if (
                native.get("question_id") != payload["question_id"]
                or native.get("revision") != payload["revision"]
            ):
                raise LbError(
                    "identity_changed: native question/revision differs", EXIT_REFUSED
                )

        def intent(fresh):
            observation.answer_intent(
                fresh,
                event_id,
                operation_id,
                mode,
                request_digest,
                correlation,
                create=True,
            )

        value, current = observation._change(doc, token, intent, dry_run=dry_run)
        answer = next(row for row in value["answers"] if row["id"] == operation_id)
        if dry_run or mode == "external":
            return {"answer": answer, "version_token": current, "dry_run": dry_run}
        try:
            receipt = herdr.submit_question(
                binding,
                {**payload, "operation_id": operation_id, "answer_digest": answer["answer_digest"]},
            )
        except (OSError, LbError, TimeoutError):
            return {"answer": answer, "version_token": current, "dry_run": False}
        if receipt is not None:
            value, current = observation._change(
                doc,
                None,
                lambda fresh: observation.answer_receipt(
                    fresh, operation_id, receipt, "adapter"
                ),
            )
        answer = next(row for row in value["answers"] if row["id"] == operation_id)
        if answer["status"] != "confirmed":
            try:
                confirmation = herdr.confirm_question(binding, answer)
            except (OSError, LbError, TimeoutError):
                return {"answer": answer, "version_token": current, "dry_run": False}
            value, current = observation._change(
                doc,
                None,
                lambda fresh: observation.answer_receipt(
                    fresh, operation_id, confirmation, "adapter"
                ),
            )
        answer = next(row for row in value["answers"] if row["id"] == operation_id)
        return {"answer": answer, "version_token": current, "dry_run": False}


def answer_reconcile(root, log, operation_id, input_file, token, dry_run):
    from contextlib import nullcontext

    from logbook_cli.adapters import herdr

    doc = load(root, log)
    value = _answer_context(doc, token)
    answer = next((row for row in value["answers"] if row["id"] == operation_id), None)
    if answer is None:
        raise LbError("invalid_transition: unknown Answer", EXIT_REFUSED)
    receipt = _input(doc, input_file) if input_file is not None else None
    with (
        observation.action_lock(doc, answer["binding"])
        if not dry_run
        else nullcontext()
    ):
        if receipt is None and answer["status"] in {"confirmed", "not_submitted"}:
            _, current = observation._change(
                doc, token, lambda fresh: None, dry_run=True
            )
            return {"answer": answer, "version_token": current, "dry_run": dry_run}
        if receipt is None:
            receipt = herdr.confirm_question(answer["binding"], answer)
        results = []

        def reconcile(fresh):
            results.append(
                observation.answer_receipt(
                    fresh,
                    operation_id,
                    receipt,
                    "caller" if input_file is not None else "adapter",
                )
            )

        _, current = observation._change(doc, token, reconcile, dry_run=dry_run)
        return {"answer": results[0], "version_token": current, "dry_run": dry_run}
