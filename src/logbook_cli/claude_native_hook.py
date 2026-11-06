"""Native Claude hook entry point; explicitly enabled by the owning repository."""

import json
import os
import sys

from logbook_cli import state
from logbook_cli.adapters import claude_questions
from logbook_cli.document import LbError


def run(payload):
    if not isinstance(payload, dict):
        raise ValueError("native hook input must be an object")
    if not os.environ.get(claude_questions.ENVIRONMENT):
        return {}
    if payload.get("tool_name") != "AskUserQuestion":
        return {}
    allowed = {
        "hook_event_name", "tool_name", "session_id", "tool_use_id",
        "tool_input", "tool_response",
    }
    native = {key: value for key, value in payload.items() if key in allowed}
    if native.get("hook_event_name") == "PreToolUse":
        return claude_questions.pre_tool(native)
    if native.get("hook_event_name") == "PostToolUse":
        return claude_questions.post_tool(native)
    return {}


def main():
    try:
        data = sys.stdin.buffer.read(claude_questions.WIRE_LIMIT + 1)
        if len(data) > claude_questions.WIRE_LIMIT:
            raise ValueError("native hook input exceeds bound")
        payload = json.loads(data, object_pairs_hook=state.unique_object)
        result = run(payload)
    except (LbError, OSError, ValueError, TypeError):
        # Failure leaves the native UI in charge; it never approves another tool.
        print("lbkit: native question callback unavailable; use native UI", file=sys.stderr)
        result = {}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
