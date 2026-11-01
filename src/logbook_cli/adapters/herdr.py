"""Herdr reads and one-shot controls, using full handles and explicit observations."""

import hashlib
import json
import os
import re
import shutil
import subprocess

from logbook_cli import records
from logbook_cli.document import EXIT_REFUSED, EXIT_USAGE, LbError


def available():
    return {
        "adapter": "herdr",
        "installed": shutil.which("herdr") is not None,
        "caller_managed": os.environ.get("HERDR_ENV") == "1",
        "session_identity": "inspect the selected recipient; not inferred from pane identity",
    }


def invoke(machine, *args, mutation=False, raw=False):
    if os.environ.get("HERDR_ENV") != "1":
        raise LbError(
            "Herdr operations require a managed caller (HERDR_ENV=1)", EXIT_REFUSED
        )
    command = ["herdr"]
    if machine != "local":
        command += ["--machine", machine]
    try:
        result = subprocess.run(
            command + list(args), capture_output=True, text=True, timeout=30
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        message = (
            "control outcome unknown; inspect before any retry"
            if mutation
            else "Herdr read unavailable"
        )
        raise LbError(message, EXIT_REFUSED) from exc
    if result.returncode:
        # Keep arbitrary terminal contents and transport details out of errors.
        raise LbError(
            "Herdr command refused; "
            + (
                "inspect side effects before retry"
                if mutation
                else "check adapter capability and target"
            ),
            EXIT_REFUSED,
        )
    if raw:
        return result.stdout
    try:
        value = json.loads(result.stdout)
        if not isinstance(value, dict):
            raise ValueError("object required")
        return value
    except ValueError as exc:
        raise LbError(
            "Herdr did not return structured output; reconcile before retry",
            EXIT_REFUSED,
        ) from exc


def session_identity(pane, agent):
    """Read native Herdr session references, never infer identity from a pane/PID."""
    identities = []
    for record in (pane, agent):
        reference = record.get("agent_session")
        if reference is not None:
            if (
                not isinstance(reference, dict)
                or not isinstance(reference.get("source"), str)
                or not reference["source"].strip()
                or not reference.get("agent")
                or reference["agent"] != record.get("agent")
                or reference["agent"] != agent.get("agent")
            ):
                return (
                    None,
                    "invalid session reference or session belongs to another agent",
                )
            if reference.get("kind") != "id":
                return (
                    None,
                    "runtime session reference is not an ID; a path is not a session ID",
                )
            identities.append(reference.get("value"))
        # Compatibility with adapters exposing the earlier flat representation.
        identities.extend(
            record[key]
            for key in ("session_id", "agent_session_id")
            if record.get(key) is not None
        )
    if not identities:
        return None, (
            "runtime session identity unavailable; inspect agent_session in `herdr agent get` "
            "and the agent's integration status; pane IDs cannot replace session IDs"
        )
    if any(not isinstance(value, str) or not value.strip() for value in identities):
        return None, "runtime session identity is empty or malformed"
    if len(set(identities)) != 1:
        return (
            None,
            "conflicting runtime session identities; inspect recipient before control",
        )
    return identities[0], None


def inspect(binding):
    machine, pane_id = binding["machine"], binding["pane_id"]
    pane = invoke(machine, "pane", "get", pane_id).get("result", {}).get("pane", {})
    agent_error = None
    try:
        agent = (
            invoke(machine, "agent", "get", pane_id).get("result", {}).get("agent", {})
        )
    except LbError:
        agent, agent_error = (
            {},
            "agent recognition unavailable; pane observation retained",
        )
    output = invoke(
        machine,
        "pane",
        "read",
        pane_id,
        "--source",
        "recent-unwrapped",
        "--lines",
        "30",
        raw=True,
    )
    session, session_gap = session_identity(pane, agent)
    actual_agent = agent.get("name") or agent.get("agent_name") or agent.get("agent")
    current = {
        "machine": machine,
        "workspace_id": pane.get("workspace_id"),
        "tab_id": pane.get("tab_id"),
        "pane_id": pane.get("pane_id"),
        "agent_id": actual_agent,
        "session_id": session,
        "state": agent.get("agent_status", pane.get("agent_status", "unknown")),
        "cwd": agent.get("foreground_cwd", pane.get("foreground_cwd")),
        "output_digest": hashlib.sha256(output.encode()).hexdigest(),
    }
    mismatches = [
        k
        for k in (
            "machine",
            "workspace_id",
            "tab_id",
            "pane_id",
            "agent_id",
            "session_id",
        )
        if current[k] != binding[k]
    ]
    digest = hashlib.sha256(json.dumps(current, sort_keys=True).encode()).hexdigest()
    return {
        "observation": current,
        "observation_token": digest,
        "pane_output": output,
        "mismatches": mismatches,
        "live_verified": bool(session) and not mismatches and agent_error is None,
        "capability_gap": session_gap,
        "agent_recognition": agent_error,
    }


def control(
    binding,
    action,
    expected_session,
    expected_observation,
    message,
    dry_run,
    before_mutation=None,
):
    current = inspect(binding)
    if not current["live_verified"] or expected_session != binding["session_id"]:
        detail = (
            current.get("capability_gap") or "recipient/session differs from binding"
        )
        raise LbError(
            f"recipient/session mismatch or missing live identity; control refused: {detail}",
            EXIT_REFUSED,
        )
    if current["observation_token"] != expected_observation:
        raise LbError(
            "recipient/input observation changed; inspect again", EXIT_REFUSED
        )
    if current["observation"]["state"] not in {"idle", "done"}:
        raise LbError("recipient is not idle; control refused", EXIT_REFUSED)
    command = (
        ["agent", "prompt", binding["pane_id"], message]
        if action == "send"
        else ["pane", "close", binding["pane_id"]]
    )
    if dry_run:
        return {
            "dry_run": True,
            "action": action,
            "observation": current["observation"],
            "effect": "none",
        }
    if before_mutation is not None:
        before_mutation()
    receipt = invoke(binding["machine"], *command, mutation=True)
    return {
        "dry_run": False,
        "action": action,
        "receipt": receipt,
        "effect": "transport operation only; not acknowledgement, task acceptance or dispatch closure",
    }


def validate_binding(item):
    for key in item:
        records.single_line(item[key], key)
    if not re.fullmatch(r"w[0-9A-Za-z]+", item["workspace_id"]):
        raise LbError("workspace must be its full stable ID", EXIT_USAGE)
    for key, prefix in (("tab_id", "t"), ("pane_id", "p")):
        if not re.fullmatch(
            re.escape(item["workspace_id"]) + ":" + prefix + r"[0-9A-Za-z]+", item[key]
        ):
            raise LbError(
                f"{key} must be workspace-qualified, never a list index", EXIT_USAGE
            )
    records.observed(item["observed_at"])
    return item


def binding_observation(binding, pane, agent):
    """Project observed native identity without filling gaps from the request."""
    from datetime import datetime, timezone

    session, gap = session_identity(pane, agent)
    if gap:
        raise LbError(gap, EXIT_REFUSED)
    observed = {
        "machine": binding["machine"],
        "server": binding["server"],
        "workspace_id": pane.get("workspace_id"),
        "tab_id": pane.get("tab_id"),
        "pane_id": pane.get("pane_id"),
        "agent_id": agent.get("name") or agent.get("agent_name") or agent.get("agent"),
        "session_id": session,
    }
    if any(not isinstance(v, str) or not v for v in observed.values()):
        raise LbError("incomplete observed binding", EXIT_REFUSED)
    return {
        "binding": observed,
        "state": agent.get("agent_status", "unknown"),
        "observed_at": datetime.now(timezone.utc).isoformat(),
    }


def validate_session_binding(binding):
    keys = {"machine", "server", "workspace_id", "tab_id", "pane_id", "agent_id", "session_id"}
    if not isinstance(binding, dict) or set(binding) != keys:
        raise LbError("binding requires complete machine/server/native identity", EXIT_USAGE)
    for key, value in binding.items():
        records.single_line(value, key)
        if len(value) > 512:
            raise LbError("binding field exceeds limit", EXIT_USAGE)
    validate_binding({**binding, "observed_at": "2000-01-01T00:00:00Z"})
    return binding


async def invoke_bounded(machine, *args, deadline, output_limit):
    """Bound both pipe buffers and child lifetime, including cancellation cleanup."""
    import asyncio
    import time

    if os.environ.get("HERDR_ENV") != "1" or deadline <= time.monotonic():
        raise LbError("managed caller and unexpired deadline required", EXIT_REFUSED)
    command = ["herdr"] + (["--machine", machine] if machine != "local" else [])

    async def cleanup(process):
        if process.returncode is not None:
            return

        async def discard(stream):
            while await stream.read(16384):
                pass

        drains = [
            asyncio.create_task(discard(process.stdout)),
            asyncio.create_task(discard(process.stderr)),
        ]
        try:
            try:
                process.terminate()
            except ProcessLookupError:
                pass
            try:
                await asyncio.wait_for(process.wait(), 1)
            except TimeoutError:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
                try:
                    await asyncio.wait_for(process.wait(), 1)
                except TimeoutError as exc:
                    raise LbError(
                        "owned Herdr child cleanup unconfirmed", EXIT_REFUSED
                    ) from exc
        finally:
            for drain in drains:
                drain.cancel()
            await asyncio.gather(*drains, return_exceptions=True)

    spawn = asyncio.create_task(
        asyncio.create_subprocess_exec(
            *command,
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    )
    try:
        process = await asyncio.shield(spawn)
    except asyncio.CancelledError:
        process = await spawn
        await cleanup(process)
        raise
    except OSError as exc:
        raise LbError("Herdr read unavailable", EXIT_REFUSED) from exc

    async def read(stream):
        chunks, size = [], 0
        while True:
            chunk = await stream.read(16384)
            if not chunk:
                return b"".join(chunks)
            size += len(chunk)
            if size > output_limit:
                raise LbError("Herdr output exceeds limit", EXIT_REFUSED)
            chunks.append(chunk)

    readers = [
        asyncio.create_task(read(process.stdout)),
        asyncio.create_task(read(process.stderr)),
    ]
    try:
        async with asyncio.timeout(max(0, deadline - time.monotonic())):
            stdout, stderr = await asyncio.gather(*readers)
            code = await process.wait()
        if code:
            try:
                if (
                    args[:2] == ("agent", "wait")
                    and json.loads(stderr).get("error", {}).get("code") == "timeout"
                ):
                    return {"wait_timeout": True}
            except (ValueError, AttributeError):
                pass
            raise LbError("Herdr read unavailable", EXIT_REFUSED)
        try:
            value = json.loads(stdout)
            if not isinstance(value, dict):
                raise ValueError("object required")
            return value
        except (ValueError, UnicodeError) as exc:
            raise LbError("Herdr returned invalid JSON", EXIT_REFUSED) from exc
    except TimeoutError as exc:
        raise LbError("Herdr read deadline expired", EXIT_REFUSED) from exc
    finally:
        for reader in readers:
            if not reader.done():
                reader.cancel()
        await asyncio.gather(*readers, return_exceptions=True)
        await cleanup(process)
