"""Record caller-attributed facts; never perform runtime handoff operations."""

import copy
import json

from logbook_cli import execution, execution_facts
from logbook_cli.document import EXIT_REFUSED, LbError, safe_path
from logbook_cli.services.common import Result, load


def context(root, log):
    return Result(execution.view(load(root, log)))


def record(root, log, input_file, token, dry_run):
    doc = load(root, log)
    try:
        payload = json.loads(
            safe_path(doc.root, input_file).read_text(),
            object_pairs_hook=execution.unique_keys,
        )
    except ValueError as exc:
        raise LbError("invalid execution record JSON", EXIT_REFUSED) from exc
    if (
        not isinstance(payload, dict)
        or set(payload) - {"name", "thinking", "advancement", "captain", "facts"}
        or not isinstance(payload.get("facts"), list)
    ):
        execution_facts.refuse(
            "record requires facts and optional execution identity; phases and verified flags are not input"
        )
    with execution.writer(doc, dry_run):
        _, _, old = execution.read(doc)
        if old is None:
            if "thinking" not in payload:
                execution_facts.refuse("initial record requires thinking")
            value = execution.initial(
                doc,
                load(root, payload["thinking"]),
                payload.get("name"),
                payload.get("advancement"),
                payload.get("captain"),
            )
        else:
            value = copy.deepcopy(old)
            for key in ("name", "advancement", "captain"):
                if key in payload and payload[key] != old[key]:
                    execution_facts.refuse(
                        "execution identity differs; do not replace existing advancement"
                    )
            if (
                "thinking" in payload
                and load(root, payload["thinking"]).path
                != execution.project(doc) / old["thinking"]
            ):
                execution_facts.refuse("Thinking binding differs")
        for fact in payload["facts"]:
            if not isinstance(fact, dict):
                execution_facts.refuse("fact must be an object")
            prior = next((f for f in value["facts"] if f["id"] == fact.get("id")), None)
            if prior is not None:
                if prior != fact:
                    execution_facts.refuse(
                        "fact ID already exists with different content"
                    )
                continue
            execution_facts.validate_fact(fact, value["facts"])
            if fact["kind"] == "transport-resolution":
                matches = [
                    op for op in value["operations"] if op["id"] == fact["operation_id"]
                ]
                if len(matches) != 1 or matches[0]["outcome"] != "unknown":
                    execution_facts.refuse(
                        "only an unknown operation can be reconciled"
                    )
                matches[0].update(
                    outcome=fact["outcome"],
                    receipt={"evidence_ref": fact["source"]["ref"]}
                    if fact["outcome"] == "submitted"
                    else None,
                    provenance="caller_reported_runtime_observation",
                )
            value["facts"].append(fact)
        return Result(execution.write(doc, value["name"], value, token, dry_run))
