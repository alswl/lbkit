"""Plain resource observations for isolated adapter and reducer tests."""


def target(number=1, state="working"):
    return {
        "binding": {
            "machine": "local",
            "server": "example-session",
            "workspace_id": "w1",
            "tab_id": "w1:t1",
            "pane_id": f"w1:p{number}",
            "agent_id": "codex",
            "session_id": f"example-native-{number}",
        },
        "baseline": {"state": state, "observed_at": "2026-01-01T00:00:00Z"},
    }


def observation(item, state):
    binding = item["binding"]
    return {
        **binding,
        "id": binding["pane_id"],
        "state": state,
        "status": state,
        "agent": binding["agent_id"],
        "agent_status": state,
        "workspace": binding["workspace_id"],
        "tab": binding["tab_id"],
        "agent_session": {
            "kind": "id",
            "source": "fixture",
            "agent": binding["agent_id"],
            "value": binding["session_id"],
        },
    }
