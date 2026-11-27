"""Pure observation reduction; runtime observations never complete business Tasks."""

import copy
import hashlib
import json


def normalized(state):
    if state == "done":
        return "idle"
    return (
        state
        if state in {"working", "idle", "blocked", "unknown", "exited"}
        else "unknown"
    )


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


def native_position(observation):
    terminal = observation.get("terminal_id")
    sequence = observation.get("state_change_seq")
    if (
        isinstance(terminal, str)
        and 0 < len(terminal) <= 512
        and (type(sequence) is int and 0 <= sequence < 2**64)
    ):
        return {"terminal_id": terminal, "state_change_seq": sequence}
    return None


def cursor_fields_valid(cursor, target):
    required = set(initial(target))
    optional = {"dispatch_id", "working_dispatch", "last_completion"}
    if not required <= cursor.keys() <= required | optional:
        return False
    return all(
        isinstance(cursor[key], str) and bool(cursor[key])
        for key in ("dispatch_id", "working_dispatch")
        if key in cursor
    ) and (
        "last_completion" not in cursor
        or (
            isinstance(cursor["last_completion"], dict)
            and native_position(cursor["last_completion"]) == cursor["last_completion"]
        )
    )


def dispatch_idle(context, position, completion, dispatch):
    baseline = dispatch["baseline"]
    if baseline is None:
        if (
            context["armed"]
            and context.get("working_dispatch") == dispatch["operation_id"]
        ):
            return "settled"
        return "observation_gap"
    if position is None or position["terminal_id"] != baseline["terminal_id"]:
        return "observation_gap"
    sequence = position["state_change_seq"]
    if sequence < baseline["state_change_seq"]:
        return "observation_gap"
    if sequence == baseline["state_change_seq"]:
        return None
    if completion:
        return "settled"
    return "observation_gap"


def observe(context, observation, *, dispatch=None):
    result = copy.deepcopy(context)
    # A retired binding must be explicitly replaced by the caller. A later
    # snapshot of the old identity cannot establish continuity across the gap.
    if result["reported"] in {"identity_changed", "exited"}:
        return result, []
    state = normalized(observation.get("state", "unknown"))
    position = native_position(observation)
    completion = (
        position is not None
        and type(observation.get("completion_seq")) is int
        and observation["completion_seq"] > 0
        and observation["completion_seq"] == position["state_change_seq"]
    )
    operation_id = dispatch["operation_id"] if dispatch is not None else None
    new_dispatch = operation_id is not None and operation_id != result.get(
        "dispatch_id"
    )
    kind = None
    dispatch_event = False
    correlation = "observed" if result["observed"] else "uncorrelated"
    if observation.get("binding") != result["binding"]:
        kind = "identity_changed"
        correlation = "lost"
        result["armed"] = False
    elif state == "working":
        result.update(armed=True, observed=True, reported=None)
        if new_dispatch:
            result["working_dispatch"] = operation_id
    elif state == "blocked":
        if result["state"] != "blocked" or result["reported"] != "needs_input":
            kind = "needs_input"
        result["armed"] = False
    elif state == "idle":
        if new_dispatch:
            kind = dispatch_idle(result, position, completion, dispatch)
            result["armed"] = False
            if kind is not None:
                result["dispatch_id"] = operation_id
                result.pop("working_dispatch", None)
                dispatch_event = True
                if kind == "observation_gap":
                    correlation = "lost"
                elif completion and position == result.get("last_completion"):
                    # An earlier sample saw the transition before receipt publication.
                    kind = None
        elif result["armed"]:
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
    if kind and (
        dispatch_event or not (result["reported"] == kind and result["state"] == state)
    ):
        if kind == "settled" and completion:
            result["last_completion"] = position
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
        if kind == "needs_input" and observation.get("question") is not None:
            events[-1]["question"] = copy.deepcopy(observation["question"])
        result["reported"] = kind
    result["state"] = state
    result["observed"] = True
    return result, events
