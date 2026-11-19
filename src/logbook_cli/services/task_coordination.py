"""Task responsibility and execution facts, independent of document projections."""

import copy

from logbook_cli import records, unified
from logbook_cli.document import EXIT_REFUSED, LbError
from logbook_cli.repository import artifact_refs, read_document, require_synced
from logbook_cli.task_identity import lookup, snapshot


def subject(value):
    if (
        not isinstance(value, dict)
        or set(value) != {"kind", "subject_id"}
        or value["kind"] not in {"human", "agent"}
    ):
        raise LbError("invalid subject kind/identity", EXIT_REFUSED)
    records.single_line(value["subject_id"], "subject_id")
    return value


def initial_runtime():
    return {
        "assignee": None,
        "assignment_revision": 0,
        "assignment_history": [],
        "current_binding_id": None,
        "execution_bindings": {},
        "result_sources": {},
    }


def assign_value(runtime, payload, unassign=False):
    if not isinstance(payload, dict) or set(payload) != (
        {"basis"} if unassign else {"subject", "basis"}
    ):
        raise LbError("assignment requires subject and basis", EXIT_REFUSED)
    records.single_line(payload["basis"], "basis")
    owner = None if unassign else subject(payload["subject"])
    if runtime.get("assignee") == owner:
        return
    runtime.setdefault("assignment_history", []).append(
        {
            "previous": runtime.get("assignee"),
            "subject": owner,
            "basis": payload["basis"],
        }
    )
    runtime["assignment_revision"] = runtime.get("assignment_revision", 0) + 1
    runtime["assignee"] = copy.deepcopy(owner)
    runtime["current_binding_id"] = None


def bind_value(runtime, payload):
    keys = {
        "id",
        "assignment_revision",
        "machine",
        "session_id",
        "adapter",
        "runtime_locator",
        "work_context",
        "input_ref",
        "basis",
        "observed_at",
    }
    if not isinstance(payload, dict) or set(payload) != keys:
        raise LbError("binding requires: " + ", ".join(sorted(keys)), EXIT_REFUSED)
    if not runtime.get("assignee") or payload["assignment_revision"] != runtime.get(
        "assignment_revision"
    ):
        raise LbError("binding requires current assignee and revision", EXIT_REFUSED)
    for key in keys - {"assignment_revision", "runtime_locator", "work_context"}:
        records.single_line(payload[key], key)
    records.observed(payload["observed_at"])
    context = payload["work_context"]
    if not isinstance(context, dict) or set(context) != {
        "repository_ref",
        "working_directory",
    }:
        raise LbError("invalid work_context", EXIT_REFUSED)
    records.single_line(context["working_directory"], "working_directory")
    if context["repository_ref"] is not None:
        records.single_line(context["repository_ref"], "repository_ref")
    if payload["adapter"] != "herdr" or not isinstance(
        payload["runtime_locator"], dict
    ):
        raise LbError("only the herdr runtime adapter is supported", EXIT_REFUSED)
    native_binding({**payload, "subject": runtime["assignee"]})
    value = copy.deepcopy(payload) | {"subject": copy.deepcopy(runtime["assignee"])}
    bindings = runtime.setdefault("execution_bindings", {})
    prior = bindings.get(payload["id"])
    if prior is not None and prior != value:
        raise LbError("binding ID is immutable", EXIT_REFUSED)
    bindings[payload["id"]] = value
    runtime["current_binding_id"] = payload["id"]


def native_binding(binding):
    from logbook_cli.adapters import herdr

    locator = binding["runtime_locator"]
    keys = {"workspace_id", "tab_id", "pane_id", "agent_id", "server"}
    if set(locator) != keys:
        raise LbError(
            "runtime_locator requires " + ", ".join(sorted(keys)), EXIT_REFUSED
        )
    item = {
        **locator,
        "machine": binding["machine"],
        "session_id": binding["session_id"],
    }
    herdr.validate_binding(
        {k: v for k, v in item.items() if k != "server"}
        | {"observed_at": binding["observed_at"], "basis": binding["basis"]}
    )
    records.single_line(item["server"], "server")
    return item


def result_value(runtime, refs, payload):
    if (
        not isinstance(payload, dict)
        or set(payload) - {"ref", "source", "version_ref", "observed_at"}
        or not {"ref", "source", "observed_at"} <= set(payload)
    ):
        raise LbError("invalid result source payload", EXIT_REFUSED)
    ref = payload["ref"]
    if ref not in refs:
        raise LbError("result ref is absent from current Task", EXIT_REFUSED)
    source = payload["source"]
    if not isinstance(source, dict):
        raise LbError("invalid source", EXIT_REFUSED)
    if set(source) == {"binding_id"}:
        if source["binding_id"] not in runtime.get("execution_bindings", {}):
            raise LbError("source binding must belong to this Task", EXIT_REFUSED)
    else:
        if set(source) != {"kind", "subject_id", "basis"}:
            raise LbError(
                "source requires binding_id or subject and basis", EXIT_REFUSED
            )
        subject({k: source[k] for k in ("kind", "subject_id")})
        records.single_line(source["basis"], "basis")
    records.observed(payload["observed_at"])
    version = payload.get("version_ref")
    if version is not None:
        records.single_line(version, "version_ref")
    value = {
        "source": source,
        "version_ref": version,
        "observed_at": payload["observed_at"],
    }
    sources = runtime.setdefault("result_sources", {})
    prior = sources.get(ref)
    if prior and (prior["source"] != source or prior["version_ref"] != version):
        raise LbError(
            "conflicting result provenance; use a distinct versioned ref", EXIT_REFUSED
        )
    if prior is None:
        sources[ref] = copy.deepcopy(value)


def mutate(root, log, task_id, input_file, execution_token, dry_run, action):
    doc = read_document(root, log)
    from logbook_cli.services.agent_observation import _input

    payload = _input(doc, input_file)
    with unified.writer(doc.root, doc.path, dry_run):
        doc, task = require_synced(root, log, task_id)
        path, value = unified.locate(doc.root, doc.path, required=True)
        if execution_token != unified.section_token(value, "execution"):
            raise LbError("execution version conflict; reread context", EXIT_REFUSED)
        runtime = copy.deepcopy(
            value["execution"]["tasks"].get(task_id, initial_runtime())
        )
        if (
            task.human
            and action in {"assign", "bind"}
            and (action == "bind" or payload.get("subject", {}).get("kind") != "human")
        ):
            raise LbError("human Task cannot be delegated to an Agent", EXIT_REFUSED)
        if action == "assign":
            assign_value(runtime, payload)
        elif action == "unassign":
            assign_value(runtime, payload, True)
        elif action == "bind":
            bind_value(runtime, payload)
        elif action == "result-source":
            result_value(runtime, artifact_refs(task), payload)
        prior = value["execution"]["tasks"].get(task_id)
        if (
            action in {"assign", "unassign", "bind"}
            and prior
            and (
                prior.get("assignee") != runtime.get("assignee")
                or prior.get("current_binding_id") != runtime.get("current_binding_id")
            )
        ):
            from logbook_cli.services.readiness import unresolved_operation

            if unresolved_operation(value["execution"], task_id):
                raise LbError(
                    "Reconcile the Task operation before changing execution binding",
                    EXIT_REFUSED,
                )
        changed = prior != runtime
        value["execution"]["tasks"][task_id] = runtime
        if changed and not dry_run:
            unified.publish(path, value)
        return {
            "changed": changed,
            "task_id": task_id,
            "runtime": runtime,
            "dry_run": dry_run,
            "version_token": execution_token
            if dry_run
            else unified.section_token(value, "execution"),
        }


def show(root, log, task_id):
    doc = read_document(root, log)
    _, value = unified.locate(doc.root, doc.path, required=True)
    runtime = value["execution"]["tasks"].get(task_id, initial_runtime())
    try:
        task, _, item = lookup(doc, task_id)
    except LbError:
        from logbook_cli.task_identity import bindings

        if task_id in bindings(doc) or task_id not in value["execution"]["tasks"]:
            raise
        return {
            "task_id": task_id,
            "detached": True,
            "runtime": runtime,
            "sync_status": doc.sync_status,
        }
    return {
        "task": snapshot(task, item),
        "runtime": runtime,
        "sync_status": doc.sync_status,
        "results": [
            {
                "ref": ref,
                "source_status": "known"
                if ref in runtime["result_sources"]
                else "unknown",
                "provenance": runtime["result_sources"].get(ref),
            }
            for ref in artifact_refs(task)
        ],
    }


def inspect(root, log, task_id, binding_id):
    from logbook_cli.adapters import herdr

    view = show(root, log, task_id)
    binding = view["runtime"]["execution_bindings"].get(binding_id)
    if binding is None:
        raise LbError("binding not found", EXIT_REFUSED)
    return {
        "binding": binding,
        "observation": herdr.inspect(native_binding(binding)),
        "sync_status": view["sync_status"],
    }
