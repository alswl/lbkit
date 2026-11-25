"""Run-scoped dependency authority and graph validation."""

from __future__ import annotations

import json
import os
from collections import deque
from pathlib import Path

from logbook_cli import state, task_identity, unified
from logbook_cli.document import EXIT_REFUSED, Document, LbError
from logbook_cli.storage import replace_bytes_at

FORMAT = "task-dependencies"
Graph = dict[str, list[str]]


def sidecar(run_path: Path) -> Path:
    return run_path.with_suffix(".dependencies.json")


def validate(graph: Graph) -> None:
    """Check all endpoints, duplicate edges and acyclicity without recursion."""
    downstream: dict[str, list[str]] = {key: [] for key in graph}
    remaining = {key: len(targets) for key, targets in graph.items()}
    for task_id, targets in graph.items():
        if len(set(targets)) != len(targets):
            raise LbError(f"duplicate dependencies for Task {task_id}", EXIT_REFUSED)
        for target in targets:
            if target not in downstream:
                raise LbError(f"unknown dependency Task ID: {target}", EXIT_REFUSED)
            downstream[target].append(task_id)

    ready = deque(key for key, count in remaining.items() if not count)
    visited = 0
    while ready:
        key = ready.popleft()
        visited += 1
        for dependent in downstream[key]:
            remaining[dependent] -= 1
            if not remaining[dependent]:
                ready.append(dependent)
    if visited != len(graph):
        raise LbError("dependency graph contains a cycle", EXIT_REFUSED)


def from_markdown(doc: Document) -> Graph:
    return {
        task_id: task_identity.dependencies(task, item)
        for task_id, (task, _, item) in task_identity.bindings(doc).items()
    }


def effective(doc: Document) -> Graph:
    graph = doc.task_dependency_graph
    return from_markdown(doc) if graph is None else graph


def decode(data: bytes, run_id: str, task_ids: set[str]) -> Graph:
    try:
        value = json.loads(data, object_pairs_hook=state.unique_object)
        if (
            not isinstance(value, dict)
            or set(value) != {"format", "run_id", "dependencies"}
            or value["format"] != FORMAT
            or value["run_id"] != run_id
            or not isinstance(value["dependencies"], list)
        ):
            raise ValueError("invalid dependency file type, Run ID or collection")
        graph: Graph = {key: [] for key in sorted(task_ids)}
        for edge in value["dependencies"]:
            if (
                not isinstance(edge, dict)
                or set(edge) != {"task_id", "depends_on"}
                or not isinstance(edge["task_id"], str)
                or not isinstance(edge["depends_on"], str)
                or edge["task_id"] not in graph
            ):
                raise ValueError("invalid dependency edge or unknown source Task")
            graph[edge["task_id"]].append(edge["depends_on"])
    except (TypeError, ValueError, RecursionError) as exc:
        raise LbError(f"invalid dependency file: {exc}", EXIT_REFUSED) from exc
    validate(graph)
    return graph


def envelope(run_id: str, graph: Graph) -> dict:
    validate(graph)
    return {
        "format": FORMAT,
        "run_id": run_id,
        "dependencies": [
            {"task_id": key, "depends_on": target}
            for key in sorted(graph)
            for target in graph[key]
        ],
    }


def load(doc: Document, run_path: Path, run: dict) -> Graph:
    if "dependency_source" not in run:
        return from_markdown(doc)
    path = sidecar(run_path)
    if run["dependency_source"] != path.name:
        raise LbError("invalid Run dependency source", EXIT_REFUSED)
    try:
        data = state.read_regular(doc.root, path)
    except OSError as exc:
        raise LbError(f"dependency file unavailable: {path.name}", EXIT_REFUSED) from exc
    return decode(data, run["identity"]["run_id"], set(task_identity.bindings(doc)))


def stage_cutover(doc: Document, run_path: Path, run: dict) -> None:
    """Stage split-task-dependencies while the caller holds the Run writer."""
    if "dependency_source" in run:
        return
    path = sidecar(run_path)
    graph = from_markdown(doc)
    if len(graph) != sum(len(stage.tasks) for stage in doc.stages):
        raise LbError("identify every Task before dependency cutover", EXIT_REFUSED)
    run_id = run["identity"]["run_id"]
    data = unified.encode(envelope(run_id, graph))
    try:
        prior = state.read_regular(doc.root, path)
    except FileNotFoundError:
        prior = None
    except OSError as exc:
        raise LbError("cannot read staged dependency file", EXIT_REFUSED) from exc
    if prior is not None and decode(prior, run_id, set(graph)) != graph:
        raise LbError("staged dependency file conflicts with current Logbook", EXIT_REFUSED)
    if prior is None:
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            replace_bytes_at(fd, path.name, data, None)
        finally:
            os.close(fd)
    # The caller publishes this marker with the actual Run update.
    run["dependency_source"] = path.name


def replace_graph(doc: Document, run_path: Path, run: dict, graph: Graph) -> None:
    """Publish one graph atomically under the Run writer lock."""
    path = sidecar(run_path)
    prior = state.read_regular(doc.root, path)
    data = unified.encode(envelope(run["identity"]["run_id"], graph))
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        replace_bytes_at(fd, path.name, data, prior)
    finally:
        os.close(fd)
