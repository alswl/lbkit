"""One-shot bounded Herdr observation; no durable state or business mutations."""

import asyncio
import base64
import json
import math
import signal
import time
from datetime import datetime, timezone

from logbook_cli import wait_state
from logbook_cli.adapters import claude_questions, herdr
from logbook_cli.document import EXIT_USAGE, LbError, root_path, safe_path
from logbook_cli.services.common import Result

LIMIT = 1024 * 1024
KEYS = {
    "machine",
    "server",
    "workspace_id",
    "tab_id",
    "pane_id",
    "agent_id",
    "session_id",
}
EVENT_KINDS = {
    "needs_input",
    "settled",
    "exited",
    "identity_changed",
    "observation_gap",
    "unavailable",
}


def unresolved_events(value, targets):
    """Carry caller-owned work separately from notification deduplication."""
    if not isinstance(value, list) or len(value) > 256:
        raise ValueError("unresolved_events must contain at most 256 events")
    unique = {}
    for event in value:
        if (
            not isinstance(event, dict)
            or event.get("binding") not in [t["binding"] for t in targets]
            or not isinstance(event.get("event_id"), str)
            or not 1 <= len(event["event_id"]) <= 512
            or event.get("kind") not in EVENT_KINDS
        ):
            raise ValueError("invalid unresolved event")
        identity = event["event_id"]
        if identity in unique and unique[identity] != event:
            raise ValueError("conflicting unresolved event identity")
        unique[identity] = event
    return list(unique.values())


def encoded(value):
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode()


def validate(value):
    if not isinstance(value, dict) or set(value) - {
        "targets",
        "after",
        "unresolved_events",
    }:
        raise ValueError(
            "request must contain targets, optional after and unresolved_events"
        )
    targets = value.get("targets")
    if not isinstance(targets, list) or not 1 <= len(targets) <= 64:
        raise ValueError("targets must contain 1..64 items")
    unique = {}
    for target in targets:
        if not isinstance(target, dict) or set(target) - {"binding", "baseline"}:
            raise ValueError("invalid target")
        binding = target.get("binding")
        if (
            not isinstance(binding, dict)
            or set(binding) != KEYS
            or any(
                not isinstance(v, str)
                or not v.strip()
                or len(v) > 512
                or "\n" in v
                or "\r" in v
                for v in binding.values()
            )
        ):
            raise ValueError("invalid binding")
        herdr.validate_session_binding(binding)
        baseline = target.get("baseline", {})
        if not isinstance(baseline, dict) or set(baseline) - {"state", "observed_at"}:
            raise ValueError("invalid baseline")
        if baseline and (
            baseline.get("state")
            not in {"working", "idle", "done", "blocked", "unknown", "exited"}
            or not isinstance(baseline.get("observed_at"), str)
        ):
            raise ValueError("invalid baseline observation")
        key = (binding["machine"], binding["server"], binding["pane_id"])
        if key in unique and unique[key] != target:
            raise ValueError("conflicting duplicate binding")
        unique[key] = target
    targets = list(unique.values())
    contexts = [wait_state.initial(t) for t in targets]
    pending = []
    if value.get("after") is not None:
        if not isinstance(value["after"], str):
            raise ValueError("invalid continuation")
        token = json.loads(base64.b64decode(value["after"], validate=True))
        if not isinstance(token, dict) or set(token) != {"contexts", "events"}:
            raise ValueError("invalid continuation fields")
        contexts, pending = token["contexts"], token["events"]
        if (
            not isinstance(contexts, list)
            or len(contexts) != len(targets)
            or not isinstance(pending, list)
            or len(pending) > 64
        ):
            raise ValueError("invalid continuation size")
        for c, t in zip(contexts, targets):
            if (
                not isinstance(c, dict)
                or set(c) != set(wait_state.initial(t))
                or c["binding"] != t["binding"]
            ):
                raise ValueError("continuation identity differs")
            if (
                not isinstance(c["armed"], bool)
                or not isinstance(c["observed"], bool)
                or type(c["sequence"]) is not int
                or not 0 <= c["sequence"] < 2**53
            ):
                raise ValueError("invalid continuation state")
            if c["state"] not in {
                "working",
                "idle",
                "blocked",
                "unknown",
                "exited",
            } or c["reported"] not in {
                None,
                "needs_input",
                "settled",
                "exited",
                "identity_changed",
                "observation_gap",
                "unavailable",
            }:
                raise ValueError("invalid continuation observation")
        for event in pending:
            if (
                not isinstance(event, dict)
                or event.get("binding") not in [t["binding"] for t in targets]
                or event.get("kind")
                not in {
                    "needs_input",
                    "settled",
                    "exited",
                    "identity_changed",
                    "observation_gap",
                    "unavailable",
                }
            ):
                raise ValueError("invalid retained event")
    pending = unresolved_events(pending, targets)
    unresolved = unresolved_events(value.get("unresolved_events", []), targets)
    # Reserve room for all targets to produce an event in this call. Refuse before
    # observation rather than losing a return after its source has changed.
    if len(unresolved) + len(pending) + len(targets) > 256:
        raise ValueError("resolve retained events before continuing observation")
    if len(encoded([targets, contexts, pending, unresolved])) * 5 > LIMIT:
        raise ValueError("request cannot fit complete reusable result")
    return targets, contexts, pending, unresolved


async def observe_all(targets, contexts, pending, unresolved, timeout, on_sample=None):
    deadline = time.monotonic() + timeout
    semaphore = asyncio.Semaphore(8)
    wake = asyncio.Event()
    interrupted = 0
    errors = set()
    scopes = {}

    async def call(machine, *args):
        async with asyncio.timeout(max(0, deadline - time.monotonic())):
            async with semaphore:
                return await herdr.invoke_bounded(
                    machine, *args, deadline=deadline, output_limit=256 * 1024
                )

    def notify(index, events):
        if on_sample is not None:
            try:
                on_sample(index, contexts[index], events)
            except Exception:
                wake.set()
                raise

    async def worker(index, target):
        binding = target["binding"]
        if contexts[index]["reported"] in {"identity_changed", "exited"}:
            return
        try:
            # Scope comes from the selected server, never a guessed --session flag.
            if binding["machine"] not in scopes:
                scopes[binding["machine"]] = asyncio.create_task(
                    call(binding["machine"], "status", "--json")
                )
            status = await asyncio.shield(scopes[binding["machine"]])
            scope = status.get("server", {})
            if (
                not isinstance(scope, dict)
                or not scope.get("running")
                or scope.get("compatible") is False
                or (scope.get("session") or "default") != binding["server"]
            ):
                raise LbError("server scope unavailable or mismatched", EXIT_USAGE)
            while time.monotonic() < deadline:
                agent_result, pane_result = await asyncio.gather(
                    call(binding["machine"], "agent", "get", binding["pane_id"]),
                    call(binding["machine"], "pane", "get", binding["pane_id"]),
                )
                agent = agent_result.get("result", {}).get("agent", {})
                pane = pane_result.get("result", {}).get("pane", {})
                observation = herdr.binding_observation(binding, pane, agent)
                if observation["binding"] == binding:
                    native = await claude_questions.observe_native(binding, deadline)
                    if native is not None:
                        observation.update(state="blocked", question=native)
                contexts[index], events = wait_state.observe(
                    contexts[index], observation
                )
                notify(index, events)
                if events:
                    pending.extend(events)
                    wake.set()
                    return
                if observation["state"] == "working":
                    remaining = min(2, deadline - time.monotonic())
                    if remaining <= 0:
                        return
                    started = time.monotonic()
                    await call(
                        binding["machine"],
                        "agent",
                        "wait",
                        binding["pane_id"],
                        "--timeout",
                        str(max(1, int(remaining * 1000))),
                    )
                    # Early native returns must not turn stale working snapshots
                    # into a subprocess heartbeat.
                    await asyncio.sleep(
                        max(0, min(started + remaining, deadline) - time.monotonic())
                    )
                else:
                    await asyncio.sleep(min(2, max(0, deadline - time.monotonic())))
        except (LbError, TimeoutError, ValueError, TypeError, AttributeError):
            if time.monotonic() >= deadline:
                return
            errors.add(index)
            if contexts[index]["reported"] == "unavailable":
                return
            contexts[index].update(reported="unavailable", state="unknown", armed=False)
            contexts[index]["sequence"] += 1
            pending.append(
                {
                    "event_id": f"unavailable-{index}-{contexts[index]['sequence']}",
                    "binding": binding,
                    "kind": "unavailable",
                    "state": "unknown",
                    "correlation": "lost",
                    "observed_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            notify(index, [pending[-1]])
            wake.set()

    loop = asyncio.get_running_loop()

    def interrupt(signum=signal.SIGINT):
        nonlocal interrupted
        interrupted = signum
        wake.set()

    for signum in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(signum, interrupt, signum)
    workers = []
    try:
        if not pending:
            order = sorted(
                range(len(targets)), key=lambda i: contexts[i]["reported"] is not None
            )
            workers = [asyncio.create_task(worker(i, targets[i])) for i in order]
            try:
                await asyncio.wait_for(wake.wait(), max(0, deadline - time.monotonic()))
            except TimeoutError:
                pass
    finally:
        for task in [*workers, *scopes.values()]:
            task.cancel()
        outcomes = await asyncio.gather(
            *workers, *scopes.values(), return_exceptions=True
        )
        for signum in (signal.SIGINT, signal.SIGTERM):
            loop.remove_signal_handler(signum)
    cleanup_errors = [
        str(outcome) for outcome in outcomes if isinstance(outcome, Exception)
    ]
    events, retained = pending[:32], pending[32:]
    unresolved = unresolved_events([*unresolved, *events], targets)
    reason = (
        "interrupted"
        if interrupted
        else "unavailable"
        if len(errors) == len(targets)
        else "change"
        if events
        else "timeout"
    )
    next_input = {
        "targets": targets,
        "unresolved_events": unresolved,
        "after": base64.b64encode(
            encoded({"contexts": contexts, "events": retained})
        ).decode(),
    }
    result = {
        "reason": reason,
        "events": events,
        "unresolved_events": unresolved,
        "pending": [
            t["binding"]
            for t in targets
            if t["binding"] not in [e["binding"] for e in events]
        ],
        "next_input": next_input,
    }
    if cleanup_errors:
        result["cleanup_errors"] = cleanup_errors
    if len(encoded(result)) > LIMIT:
        raise LbError("complete result exceeds size limit", EXIT_USAGE)
    return Result(
        result,
        code=128 + int(interrupted)
        if interrupted
        else 1
        if reason == "unavailable" or cleanup_errors
        else 0,
    )


def wait(
    root,
    input_file=None,
    timeout=None,
    log=None,
    token=None,
    stream=False,
    dry_run=False,
):
    if log is not None:
        if input_file is not None:
            raise LbError("managed wait forbids --input-file", EXIT_USAGE)
        if token is None:
            raise LbError("managed wait requires --expect-version", EXIT_USAGE)
        return managed_wait(root, log, timeout, token, dry_run, stream=stream)
    if stream or token is not None or dry_run:
        raise LbError(
            "--stream/--expect-version/--dry-run require managed --log", EXIT_USAGE
        )
    if input_file is None:
        raise LbError("raw wait requires --input-file", EXIT_USAGE)
    try:
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be finite and positive")
        path = safe_path(root_path(root), input_file)
        with path.open("rb") as handle:
            raw = handle.read(LIMIT + 1)
        if len(raw) > LIMIT:
            raise ValueError("wait input exceeds size limit")
        targets, contexts, pending, unresolved = validate(json.loads(raw))
    except (ValueError, TypeError, KeyError) as exc:
        raise LbError(str(exc), EXIT_USAGE) from exc
    return asyncio.run(observe_all(targets, contexts, pending, unresolved, timeout))


def managed_wait(root, log, timeout, token, dry_run, *, stream=False):
    import copy
    import hashlib
    import uuid

    from logbook_cli import observation
    from logbook_cli.document import EXIT_REFUSED
    from logbook_cli.render import emit_jsonl
    from logbook_cli.services.common import load

    if not math.isfinite(timeout) or timeout <= 0:
        raise LbError("timeout must be finite and positive", EXIT_USAGE)
    deadline = time.monotonic() + timeout
    doc = load(root, log)
    initial, current = observation.read(doc)
    if initial is None:
        raise LbError("observation_not_configured: configure before wait", EXIT_REFUSED)
    if current != token:
        raise LbError("version_conflict: reread observation context", EXIT_REFUSED)
    if dry_run:
        observation.admit(initial)
        return Result({"dry_run": True, "version_token": current})
    invocation = uuid.uuid4().hex
    targets = copy.deepcopy(initial["targets"])
    contexts = copy.deepcopy(initial["contexts"])
    new_events = []
    failures = []

    def start(value):
        previous = value.get("listener", {})
        if previous.get("status") == "active":
            binding = targets[0]["binding"]
            digest = hashlib.sha256(encoded(binding)).hexdigest()
            gap = {
                "id": value["id"]
                + ":"
                + digest
                + ":gap-"
                + str(previous.get("invocation_id")),
                "observation": {
                    "event_id": "gap-" + str(previous.get("invocation_id")),
                    "kind": "observation_gap",
                    "state": "unknown",
                    "correlation": "lost",
                    "binding": copy.deepcopy(binding),
                    "abandoned_invocation": previous.get("invocation_id"),
                },
                "handling": "pending",
                "history": [],
            }
            value["events"].append(gap)
            new_events.append(copy.deepcopy(gap))
        value["listener"] = {
            "invocation_id": invocation,
            "status": "active",
            "generation": value.get("listener", {}).get("generation", 0) + 1,
        }

    def sample(index, cursor, events):
        def merge(value):
            if (
                value.get("listener", {}).get("invocation_id") != invocation
                or value["targets"] != targets
            ):
                raise LbError(
                    "invalid_transition: listener generation changed", EXIT_REFUSED
                )
            value["contexts"][index] = copy.deepcopy(cursor)
            existing = {event["id"] for event in value["events"]}
            for event in events:
                binding = hashlib.sha256(encoded(event["binding"])).hexdigest()
                key = value["id"] + ":" + binding + ":" + event["event_id"]
                if key not in existing:
                    saved = {
                        "id": key,
                        "observation": copy.deepcopy(event),
                        "handling": "pending",
                        "history": [],
                    }
                    value["events"].append(saved)
                    existing.add(key)

        try:
            value, committed_token = observation._change(doc, None, merge)
            seen = {event["id"] for event in new_events}
            added = [
                copy.deepcopy(event)
                for event in value["events"]
                if event["id"] not in seen and event["observation"] in events
            ]
            new_events.extend(added)
            if stream:
                for event in added:
                    emit_jsonl(
                        {
                            "type": "event",
                            "observation_id": value["id"],
                            "invocation_id": invocation,
                            "event_key": event["id"],
                            "kind": event["observation"]["kind"],
                            "target_key": hashlib.sha256(
                                encoded(event["observation"]["binding"])
                            ).hexdigest(),
                            "version_token": committed_token,
                        }
                    )
        except Exception as exc:
            failures.append(exc)
            raise RuntimeError("observation commit/output failed") from exc

    def finish(value):
        if value.get("listener", {}).get("invocation_id") == invocation:
            value["listener"]["status"] = "ended"

    async def run_listener():
        while True:
            result = await observe_all(
                targets, contexts, [], [], max(0, deadline - time.monotonic()), sample
            )
            if failures:
                raise failures[0]
            if (
                not stream
                or time.monotonic() >= deadline
                or result.value["reason"] in {"interrupted", "unavailable"}
            ):
                return result

    with observation.listener_lock(doc, create=True):
        started, started_token = observation._change(doc, token, start, new_work=True)
        try:
            if stream:
                for event in new_events:
                    emit_jsonl(
                        {
                            "type": "event",
                            "observation_id": started["id"],
                            "invocation_id": invocation,
                            "event_key": event["id"],
                            "kind": event["observation"]["kind"],
                            "target_key": hashlib.sha256(
                                encoded(event["observation"]["binding"])
                            ).hexdigest(),
                            "version_token": started_token,
                        }
                    )
            result = asyncio.run(run_listener())
        finally:
            value, current = observation._change(doc, None, finish)
    if stream:
        emit_jsonl(
            {
                "type": "listener_end",
                "observation_id": value["id"],
                "invocation_id": invocation,
                "reason": "cancelled"
                if result.value["reason"] == "interrupted"
                else "failed"
                if result.code
                else "timeout",
                "version_token": current,
            }
        )
    return Result(
        {
            "reason": "change"
            if new_events and result.value["reason"] == "timeout" and not stream
            else result.value["reason"],
            "invocation_id": invocation,
            "new_events": new_events,
            "unresolved_events": [
                event for event in value["events"] if event["handling"] != "resolved"
            ],
            "pending_answers": [
                answer
                for answer in value["answers"]
                if answer["status"] in {"unknown", "submitted"}
            ],
            "version_token": current,
        },
        code=result.code,
    )
