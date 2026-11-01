"""Pure observation reduction; runtime observations never complete business Tasks."""

import copy
import hashlib
import json


def normalized(state):
    if state == "done":
        return "idle"
    return state if state in {"working", "idle", "blocked", "unknown", "exited"} else "unknown"


def initial(target):
    baseline = target.get("baseline", {})
    state = normalized(baseline.get("state", "unknown"))
    return {
        "binding": copy.deepcopy(target["binding"]),
        "state": state,
        "armed": state == "working",
        "sequence": 0,
        "reported": None,
        "observed": bool(baseline),
    }


def observe(context, observation):
    result = copy.deepcopy(context)
    # A retired binding must be explicitly replaced by the caller. A later
    # snapshot of the old identity cannot establish continuity across the gap.
    if result["reported"] in {"identity_changed", "exited"}:
        return result, []
    state = normalized(observation.get("state", "unknown"))
    kind = None
    correlation = "observed" if result["observed"] else "uncorrelated"
    if observation.get("binding") != result["binding"]:
        kind = "identity_changed"
        correlation = "lost"
        result["armed"] = False
    elif state == "working":
        result.update(armed=True, observed=True, reported=None)
    elif state == "blocked":
        if result["state"] != "blocked" or result["reported"] != "needs_input":
            kind = "needs_input"
        result["armed"] = False
    elif state == "idle":
        if result["armed"]:
            kind = "settled"
            result["armed"] = False
        elif result["reported"] is None:
            kind = "observation_gap"
            correlation = "uncorrelated"
    elif state == "exited":
        kind = "exited"
        result["armed"] = False
    else:
        kind = "observation_gap"
        correlation = "lost"
        result["armed"] = False
    events = []
    if kind and not (result["reported"] == kind and result["state"] == state):
        result["sequence"] += 1
        identity = json.dumps(
            [result["binding"], result["sequence"], kind], sort_keys=True
        )
        events.append(
            {
                "event_id": hashlib.sha256(identity.encode()).hexdigest(),
                "binding": copy.deepcopy(result["binding"]),
                "kind": kind,
                "state": state,
                "correlation": correlation,
                "observed_at": observation.get("observed_at"),
            }
        )
        result["reported"] = kind
    result["state"] = state
    result["observed"] = True
    return result, events
