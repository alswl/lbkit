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
        return json.loads(result.stdout)
    except ValueError as exc:
        raise LbError(
            "Herdr did not return structured output; reconcile before retry",
            EXIT_REFUSED,
        ) from exc


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
    session = (
        agent.get("session_id")
        or agent.get("agent_session_id")
        or pane.get("agent_session_id")
    )
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
        "live_verified": not mismatches,
        "capability_gap": None
        if session
        else "runtime does not expose a verifiable agent session ID",
        "agent_recognition": agent_error,
    }


def control(binding, action, expected_session, expected_observation, message, dry_run):
    current = inspect(binding)
    if not current["live_verified"] or expected_session != binding["session_id"]:
        raise LbError(
            "recipient/session mismatch or missing live identity; control refused",
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
