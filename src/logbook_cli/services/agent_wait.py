"""One-shot bounded Herdr observation; no durable state or business mutations."""

import asyncio
import base64
import json
import math
import signal
import time
from datetime import datetime, timezone

from logbook_cli import wait_state
from logbook_cli.adapters import herdr
from logbook_cli.document import EXIT_REFUSED, EXIT_USAGE, LbError, root_path, safe_path
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


def encoded(value):
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode()


def validate(value):
    if not isinstance(value, dict) or set(value) - {"targets", "after"}:
        raise ValueError("request must contain targets and optional after")
    targets = value.get("targets")
    if not isinstance(targets, list) or not 1 <= len(targets) <= 64:
        raise ValueError("targets must contain 1..64 items")
    unique = {}
    for target in targets:
        if not isinstance(target, dict) or set(target) - {
            "binding",
            "baseline",
            "rearm",
        }:
            raise ValueError("invalid target")
        if type(target.get("rearm", False)) is not bool:
            raise ValueError("rearm must be boolean")
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
    rearm = [t.get("rearm", False) for t in unique.values()]
    targets = [{k: v for k, v in t.items() if k != "rearm"} for t in unique.values()]
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
    for index, requested in enumerate(rearm):
        if requested:
            binding = targets[index]["binding"]
            if any(e["binding"] == binding for e in pending):
                raise ValueError(
                    "deliver retained events before rearming their binding"
                )
            # A new assignment is not proof that working was observed. Keep the
            # event sequence so a later cycle cannot reuse a delivered event ID.
            fresh = wait_state.initial({"binding": binding})
            fresh["sequence"] = contexts[index]["sequence"]
            contexts[index] = fresh
    if len(encoded([targets, contexts, pending])) * 5 > LIMIT:
        raise ValueError("request cannot fit complete reusable result")
    return targets, contexts, pending


async def observe_all(targets, contexts, pending, timeout):
    deadline = time.monotonic() + timeout
    semaphore = asyncio.Semaphore(8)
    wake = asyncio.Event()
    interrupted = False
    errors = set()
    scopes = {}
    watching = [i for i, context in enumerate(contexts) if context["reported"] is None]

    async def call(machine, *args):
        async with asyncio.timeout(max(0, deadline - time.monotonic())):
            async with semaphore:
                return await herdr.invoke_bounded(
                    machine, *args, deadline=deadline, output_limit=256 * 1024
                )

    async def worker(index, target):
        binding = target["binding"]
        if contexts[index]["reported"] is not None:
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
                contexts[index], events = wait_state.observe(
                    contexts[index], observation
                )
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
            wake.set()

    loop = asyncio.get_running_loop()

    def interrupt():
        nonlocal interrupted
        interrupted = True
        wake.set()

    loop.add_signal_handler(signal.SIGINT, interrupt)
    workers = []
    try:
        if not pending and watching:
            workers = [asyncio.create_task(worker(i, targets[i])) for i in watching]
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
        loop.remove_signal_handler(signal.SIGINT)
    cleanup_errors = [
        str(outcome) for outcome in outcomes if isinstance(outcome, Exception)
    ]
    events, retained = pending[:32], pending[32:]
    reason = (
        "interrupted"
        if interrupted
        else "unavailable"
        if watching and len(errors) == len(watching)
        else "change"
        if events
        else "drained"
        if not watching
        else "timeout"
    )
    next_input = {
        "targets": targets,
        "after": base64.b64encode(
            encoded({"contexts": contexts, "events": retained})
        ).decode(),
    }
    result = {
        "reason": reason,
        "events": events,
        "next_action": "handle_events"
        if events
        else "stop_waiting"
        if reason in {"drained", "interrupted", "unavailable"} or cleanup_errors
        else "wait",
        "pending": [
            t["binding"]
            for t, context in zip(targets, contexts)
            if context["reported"] is None
            or any(e["binding"] == t["binding"] for e in retained)
        ],
        "next_input": next_input,
    }
    if cleanup_errors:
        result["cleanup_errors"] = cleanup_errors
    if len(encoded(result)) > LIMIT:
        raise LbError("complete result exceeds size limit", EXIT_USAGE)
    return Result(
        result,
        code=130
        if interrupted
        else 1
        if reason == "unavailable" or cleanup_errors
        else 0,
    )


def wait(root, input_file, timeout):
    import fcntl

    try:
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be finite and positive")
        path = safe_path(root_path(root), input_file)
        with path.open("rb") as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise LbError(
                    "wait already running for this input file", EXIT_REFUSED
                ) from exc
            raw = handle.read(LIMIT + 1)
            if len(raw) > LIMIT:
                raise ValueError("wait input exceeds size limit")
            targets, contexts, pending = validate(json.loads(raw))
            return asyncio.run(observe_all(targets, contexts, pending, timeout))
    except (ValueError, TypeError, KeyError) as exc:
        raise LbError(str(exc), EXIT_USAGE) from exc
