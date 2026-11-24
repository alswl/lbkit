"""Project a Logbook's reviewable scope independently of execution status."""

import re

from logbook_cli import repository, task_identity, unified
from logbook_cli.document import EXIT_REFUSED, TASK_RE, LbError, visible_lines, workdirs
from logbook_cli.models import Field

THEMATIC_BREAK = re.compile(r" {0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*")
LIST_MARKER = r"(?:[-+*]|[0-9]{1,9}[.)])"
LIST_ITEM = re.compile(rf"^( {{0,3}}{LIST_MARKER})(?:[ \t]+|(?=\r?$))")
GOAL = re.compile(
    r"^ {0,3}(目标|Goal)[ \t]*[:：][ \t]*(\S.*)",
    re.IGNORECASE,
)


def _goals(lines):
    goals = []
    visible_by_index = dict(visible_lines(lines))
    child_indent = 0
    for index, raw in enumerate(lines):
        if not raw.strip():
            continue
        expanded = raw.expandtabs(4)
        indent = len(expanded) - len(expanded.lstrip(" "))
        if indent < child_indent:
            child_indent = 0
        visible = visible_by_index.get(index)
        # Physical outdents end a list item even when visibility hides the line.
        if child_indent or visible is None:
            continue
        # Markdown gives a thematic break precedence over a list marker.
        if THEMATIC_BREAK.fullmatch(raw.rstrip("\r\n")):
            continue
        # A task owns all following indented lines in the Logbook parser.
        if indent == 0 and TASK_RE.match(visible):
            child_indent = 1
            continue
        if item := LIST_ITEM.match(visible):
            marker_width = len(item[1])
            padding = len(item[0].expandtabs(4)) - marker_width
            # Five or more columns after the marker start indented code.
            if not 1 <= padding <= 4:
                child_indent = marker_width + 1
                continue
            child_indent = marker_width + padding
            visible = visible[item.end() :]
        if match := GOAL.match(visible):
            label, text = match.groups()
            prefix = "目标：" if label == "目标" else "Goal:"
            goals.append(f"{prefix} {text.rstrip()}")
    return goals


def route_scope(doc):
    anchors = {
        task.line: key for key, (task, _, _) in task_identity.bindings(doc).items()
    }
    stages = []
    delivery_goals = {}
    for index, stage in enumerate(doc.stages):
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
            entry = {"stage": stage.title, "tasks": tasks}
            if stage.is_delivery:
                end = (
                    doc.stages[index + 1].line - 1
                    if index + 1 < len(doc.stages)
                    else len(doc.lines)
                )
                goals = _goals(doc.lines[stage.line : end])
                if goals:
                    entry["goals"] = goals
                    delivery_goals.update((task["task_id"], goals) for task in tasks)
            stages.append(entry)
    overview_end = next(
        (s.line - 1 for s in doc.stages if s.is_delivery), len(doc.lines)
    )
    goals = _goals(doc.lines[:overview_end])
    directories = workdirs(doc)
    reviewed_directories = [
        {
            **{
                key: value
                for key, value in group.items()
                if key not in {"line", "paths"}
            },
            "paths": [path["path"] for path in group["paths"]],
        }
        for group in directories
    ]
    scope = {"goals": goals, "directories": directories, "stages": stages}
    review = {
        **scope,
        "directories": reviewed_directories,
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
                "directories": reviewed_directories,
                "tasks": [
                    (
                        {**item, "stage_goals": delivery_goals[identity]}
                        if identity in delivery_goals
                        else item
                    )
                    for identity, item in ordered.items()
                    if identity in relevant
                ],
            }
        )
    return {
        "route_ref": unified.digest(review),
        "source_digest": repository.source_digest(doc.data),
        "task_scopes": task_scopes,
        **scope,
    }
