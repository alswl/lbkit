"""Project a Logbook's reviewable scope independently of execution status."""

import re

from logbook_cli import repository, task_identity, unified
from logbook_cli.document import EXIT_REFUSED, LbError, visible_lines, workdirs
from logbook_cli.models import Field


def route_scope(doc):
    anchors = {
        task.line: key for key, (task, _, _) in task_identity.bindings(doc).items()
    }
    stages = []
    for stage in doc.stages:
        tasks = []
        for task in stage.tasks:
            key = anchors.get(task.line)
            if not key:
                raise LbError(
                    f"identify task at line {task.line} before confirming route",
                    EXIT_REFUSED,
                )
            tasks.append(
                {
                    "task_id": key,
                    "text": task.text.strip(),
                    "criteria_digest": task_identity.criteria(task),
                    "human": task.human,
                    "repositories": task.repositories,
                    "dependencies": task_identity.dependencies(task),
                    "criteria": [
                        (annotation.kind.value, annotation.value.strip())
                        for annotation in task.annotations
                        if annotation.kind
                        in {Field.ACCEPTANCE, Field.SOURCE, Field.HANDOFF}
                    ],
                }
            )
        if stage.is_delivery or tasks:
            stages.append({"stage": stage.title, "tasks": tasks})
    overview_end = next(
        (s.line - 1 for s in doc.stages if s.is_delivery), len(doc.lines)
    )
    goals = [
        visible.strip()
        for _, visible in visible_lines(doc.lines[:overview_end])
        if visible and re.match(r"^\s*(?:[-*]\s+)?(?:目标|Goal)\s*[:：]", visible, re.I)
    ]
    scope = {"goals": goals, "directories": workdirs(doc), "stages": stages}
    review = {
        **scope,
        "stages": [
            {
                **stage,
                "tasks": [
                    {k: v for k, v in task.items() if k != "criteria_digest"}
                    for task in stage["tasks"]
                ],
            }
            for stage in stages
        ],
    }
    ordered = {
        task["task_id"]: {**task, "stage": stage["stage"]}
        for stage in review["stages"]
        for task in stage["tasks"]
    }
    task_scopes = {}
    preceding: set[str] = set()
    for key, task in ordered.items():
        preceding.add(key)
        if task["human"]:
            continue
        relevant = set(preceding)
        pending = list(relevant)
        while pending:
            for dependency in ordered[pending.pop()]["dependencies"]:
                if dependency not in ordered:
                    raise LbError(
                        f"unknown route dependency: {dependency}", EXIT_REFUSED
                    )
                if dependency not in relevant:
                    relevant.add(dependency)
                    pending.append(dependency)
        task_scopes[key] = unified.digest(
            {
                "goals": goals,
                "directories": scope["directories"],
                "tasks": [
                    item for identity, item in ordered.items() if identity in relevant
                ],
            }
        )
    return {
        "route_ref": unified.digest(review),
        "source_digest": repository.source_digest(doc.data),
        "task_scopes": task_scopes,
        **scope,
    }
