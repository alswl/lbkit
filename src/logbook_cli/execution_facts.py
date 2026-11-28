"""Validate attributed domain facts and derive policy, never certify their truth."""

from logbook_cli.document import EXIT_REFUSED, LbError


def refuse(message):
    raise LbError(message, EXIT_REFUSED)


def fields(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys.split()):
        refuse("invalid execution fact fields: expected " + keys)


def text(value):
    if (
        not isinstance(value, str)
        or not value.strip()
        or "\n" in value
        or "\r" in value
    ):
        refuse("execution evidence/identity must be a nonempty single line")


def source(value, kinds):
    if not isinstance(value, dict):
        refuse("missing evidence source")
    fields(
        value,
        "kind ref verifier subject"
        if value.get("kind") == "verified_result"
        else "kind ref",
    )
    if value["kind"] not in kinds:
        refuse("inapplicable evidence source")
    for v in value.values():
        text(v)


def referenced(facts, identity, kind):
    matches = [f for f in facts if f["id"] == identity and f["kind"] == kind]
    if len(matches) != 1:
        refuse("missing or wrong-kind prior fact reference: " + str(identity))
    return matches[0]


def target_key(record):
    return (
        "task_id" if isinstance(record, dict) and record.get("scope") == "task"
        else "dispatch_id"
    )


def validate_handoff_operation(fact, release, execution):
    """Validate a current Task handoff against its persisted transport and binding."""
    if release["scope"] != "task":
        return
    from logbook_cli.unified import digest

    task_id = release["task_id"]
    op = execution["operations"].get(fact.get("operation_id"))
    request = op["request"] if op else {}
    runtime = execution["tasks"].get(task_id, {})
    binding_id = runtime.get("current_binding_id")
    binding = runtime.get("execution_bindings", {}).get(binding_id)
    if (
        op is None
        or op["outcome"] == "not_submitted"
        or request.get("release_id") != release["id"]
        or request.get("task_id") != task_id
        or request.get("recipient") != release["recipient"]
        or binding is None
        or request.get("binding_id") != binding_id
        or request.get("session_id") != binding["session_id"]
        or request.get("binding_digest") != digest(binding)
        or any(
            other["outcome"] != "not_submitted"
            and other["request"].get("release_id") == release["id"]
            and other["request"].get("binding_id") == binding_id
            for key, other in execution["operations"].items()
            if key != op["id"]
        )
    ):
        refuse("handoff must match the effective release, send and current recipient binding")
    if op["outcome"] != "submitted" and (
        fact["receipt"]["status"] == "accepted"
        or fact["ownership"]["status"] == "recipient"
    ):
        refuse("reconcile unknown handoff delivery before recording acceptance or ownership")


def validate_fact(fact, prior):
    if not isinstance(fact, dict):
        refuse("execution fact must be an object")
    kind = fact.get("kind")
    shape = (
        {
            "takeover": "id kind source origin release_condition",
            "ownership": "id kind source takeover_id owner conflicts settled",
            "condition-result": "id kind source takeover_id condition_id satisfied",
            "delegation-release": "id kind source takeover_id " + target_key(fact)
            + " recipient scope condition_result_id",
            "handoff": "id kind release_id receipt execution_ready monitor_ready ownership",
            "transport-resolution": "id kind source operation_id outcome",
            "business-action": "id kind source operation_id outcome",
        }.get(kind)
        if isinstance(kind, str)
        else None
    )
    if not shape:
        refuse("unsupported execution fact kind")
    if kind == "handoff":
        release = referenced(prior, fact.get("release_id"), "delegation-release")
        if release["scope"] == "task":
            shape += " operation_id"
    fields(fact, shape)
    text(fact["id"])
    if kind == "takeover":
        if fact["origin"] not in ("explicit", "automatic"):
            refuse("invalid takeover origin")
        source(
            fact["source"],
            ("human_instruction",)
            if fact["origin"] == "explicit"
            else ("caller_judgment",),
        )
        condition = fact["release_condition"]
        if condition is not None:
            key = target_key(condition)
            fields(condition, "id source " + key + " recipient scope")
            source(
                condition["source"],
                ("human_instruction",)
                if fact["origin"] == "explicit"
                else ("human_instruction", "caller_judgment"),
            )
            if fact["origin"] == "automatic" and condition["scope"] == "advancement":
                refuse("automatic exit cannot release the whole advancement")
            for field in ("id", key, "recipient"):
                text(condition[field])
            if condition["scope"] not in ("dispatch", "advancement", "task"):
                refuse("invalid authorized condition scope")
        current = project(prior)
        if fact["origin"] == "automatic" and current["restricted"]:
            refuse("automatic takeover cannot replace a retained restriction")
    elif kind in ("ownership", "condition-result", "delegation-release"):
        takeover = referenced(prior, fact["takeover_id"], "takeover")
        if project(prior)["takeover"]["id"] != takeover["id"]:
            refuse("fact refers to a superseded takeover")
        if kind == "ownership":
            source(fact["source"], ("runtime_observation", "caller_judgment"))
            text(fact["owner"])
            if type(fact["conflicts"]) is not bool or type(fact["settled"]) is not bool:
                refuse("ownership requires explicit conflict and settled observations")
        elif kind == "condition-result":
            source(fact["source"], ("verified_result",))
            condition = takeover["release_condition"]
            if (
                condition is None
                or condition["id"] != fact["condition_id"]
                or type(fact["satisfied"]) is not bool
            ):
                refuse("check does not match a previously authorized condition")
        else:
            source(fact["source"], ("human_instruction", "caller_judgment"))
            for key in (target_key(fact), "recipient"):
                text(fact[key])
            if fact["scope"] not in ("dispatch", "advancement", "task"):
                refuse("invalid delegation scope")
            if fact["source"]["kind"] != "human_instruction":
                check = referenced(
                    prior, fact["condition_result_id"], "condition-result"
                )
                condition = takeover["release_condition"]
                if (
                    not check["satisfied"]
                    or check["takeover_id"] != takeover["id"]
                    or condition is None
                    or any(
                        fact[k] != condition.get(k)
                        for k in (target_key(fact), "recipient", "scope")
                    )
                ):
                    refuse("release exceeds the satisfied human-authorized condition")
            elif fact["condition_result_id"] is not None:
                refuse("direct human release does not require a condition check")
    elif kind == "handoff":
        release = referenced(prior, fact["release_id"], "delegation-release")
        current = project(
            prior, task_id=release.get("task_id"), dispatch_id=release.get("dispatch_id")
        )
        if current["release"] is None or current["release"]["id"] != release["id"]:
            refuse("handoff refers to a superseded release")
        if release["scope"] == "task":
            text(fact["operation_id"])
        for key, values in {
            "receipt": ("accepted", "unknown", "rejected"),
            "execution_ready": ("ready", "unknown", "not_ready"),
            "monitor_ready": ("ready", "unknown", "not_ready"),
            "ownership": ("recipient", "captain", "unknown", "conflict"),
        }.items():
            fields(fact[key], "status source")
            if fact[key]["status"] not in values:
                refuse("invalid handoff observation")
            source(fact[key]["source"], ("runtime_observation", "caller_judgment"))
    elif kind == "business-action":
        source(fact["source"], ("runtime_observation",))
        text(fact["operation_id"])
        if fact["outcome"] not in ("started", "not_started"):
            refuse("business-action evidence requires a definite observed outcome")
    else:
        source(fact["source"], ("runtime_observation",))
        text(fact["operation_id"])
        if fact["outcome"] not in ("submitted", "not_submitted"):
            refuse("transport reconciliation requires a definite observed outcome")


def validate_new_fact(fact, prior):
    """Apply admission rules while keeping historical facts readable."""
    validate_fact(fact, prior)
    if fact["kind"] == "takeover" and fact["origin"] == "automatic":
        refuse("new takeover requires an explicit human instruction")
    if (
        fact["kind"] == "delegation-release"
        and fact["source"]["kind"] == "caller_judgment"
    ):
        takeover = referenced(prior, fact["takeover_id"], "takeover")
        if takeover["release_condition"]["source"]["kind"] != "human_instruction":
            refuse(
                "new release requires a human instruction or a human-authorized condition"
            )


def project(facts, execution=None, *, task_id=None, dispatch_id=None):
    takeover = ownership = release = handoff = None
    for fact in facts:
        kind = fact["kind"]
        if kind == "takeover":
            takeover, ownership, release, handoff = fact, None, None, None
        elif kind == "ownership":
            ownership, handoff = fact, None
        elif kind == "delegation-release":
            scope = fact["scope"]
            if (task_id is not None or dispatch_id is not None) and not (
                scope == "advancement"
                or (scope == "task" and fact["task_id"] == task_id)
                or (scope == "dispatch" and dispatch_id is not None)
            ):
                continue
            release, handoff = fact, None
        elif kind == "handoff" and release and fact.get("release_id") == release.get("id"):
            handoff = fact
    if handoff and release["scope"] == "task":
        if execution is None:
            handoff = None
        else:
            try:
                validate_handoff_operation(handoff, release, execution)
            except LbError:
                handoff = None
    complete = bool(
        handoff
        and all(
            handoff[k]["status"] == status
            and handoff[k]["source"]["kind"] == "runtime_observation"
            for k, status in {
                "receipt": "accepted",
                "execution_ready": "ready",
                "monitor_ready": "ready",
                "ownership": "recipient",
            }.items()
        )
    )
    safe = bool(
        ownership
        and ownership["source"]["kind"] == "runtime_observation"
        and not ownership["conflicts"]
        and ownership["settled"]
    )
    if handoff and not complete:
        ownership_status = handoff["ownership"]["status"]
        if ownership_status == "conflict" or (
            release["scope"] != "task" and ownership_status != "captain"
        ):
            safe = False
    return {
        "takeover": takeover,
        "ownership": ownership,
        "release": release,
        "handoff": handoff,
        "handoff_reported_complete": complete,
        "reported_owner": release["recipient"]
        if complete
        else ownership["owner"]
        if safe
        else "unknown",
        "restricted": bool(
            takeover
            and not (release and release["scope"] == "advancement" and complete)
        ),
    }
