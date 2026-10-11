"""Task command group; business rules live in services.tasks."""

import click

from logbook_cli.commands.common import (
    DECISION,
    DRY_RUN,
    JSON,
    LOG,
    PROJECTS,
    ROOT,
    STAGE,
    TASK,
    TEXT,
    TOKEN,
    finish,
    options,
    resolve_root,
)
from logbook_cli.format import NOTE_KINDS
from logbook_cli.services import tasks


@click.group(help="Query or safely edit logbook tasks.")
@ROOT
def task(root: str | None) -> None:
    pass


@task.command("list")
@options(
    ROOT,
    PROJECTS,
    click.argument("log", required=False),
    click.option("--stage"),
    click.option(
        "--status", type=click.Choice(["todo", "in-progress", "done", "skipped"])
    ),
    click.option("--human", is_flag=True),
    JSON,
)
def list_tasks(
    root: str | None,
    projects_dir: str,
    log: str | None,
    stage: str | None,
    status: str | None,
    human: bool,
    json: bool,
) -> None:
    finish(
        tasks.list_tasks(resolve_root(root), log, projects_dir, stage, status, human),
        json,
        "tasks",
    )


@task.command("next")
@options(ROOT, LOG, JSON)
def next_task(root: str | None, log: str, json: bool) -> None:
    finish(tasks.next_task(resolve_root(root), log), json, "next")


@task.command("add")
@options(
    ROOT,
    LOG,
    STAGE,
    TEXT,
    TOKEN,
    DRY_RUN,
    JSON,
    click.option("--before-line", type=int),
    click.option("--before-task"),
)
def add(
    root: str | None,
    log: str,
    stage: str,
    text: str,
    token: str,
    dry_run: bool,
    json: bool,
    before_line: int | None,
    before_task: str | None,
) -> None:
    finish(
        tasks.add(
            resolve_root(root),
            log,
            stage,
            text,
            token,
            dry_run,
            before_line,
            before_task,
        ),
        json,
    )


@task.command("update")
@options(
    ROOT,
    LOG,
    STAGE,
    TASK,
    TOKEN,
    DRY_RUN,
    JSON,
    click.option("--status", required=True),
)
def update(
    root: str | None,
    log: str,
    stage: str,
    task: str,
    token: str,
    dry_run: bool,
    json: bool,
    status: str,
) -> None:
    finish(
        tasks.update(resolve_root(root), log, stage, task, status, token, dry_run), json
    )


@task.command("artifact")
@options(
    ROOT,
    LOG,
    STAGE,
    TASK,
    TOKEN,
    DRY_RUN,
    JSON,
    click.option("--artifact", required=True),
)
def artifact(
    root: str | None,
    log: str,
    stage: str,
    task: str,
    token: str,
    dry_run: bool,
    json: bool,
    artifact: str,
) -> None:
    finish(
        tasks.note(
            resolve_root(root), log, stage, task, artifact, "产物", token, dry_run
        ),
        json,
    )


@task.command("note")
@options(
    ROOT,
    LOG,
    STAGE,
    TASK,
    TOKEN,
    DRY_RUN,
    JSON,
    TEXT,
    click.option("--kind", type=click.Choice(NOTE_KINDS)),
)
def note(
    root: str | None,
    log: str,
    stage: str,
    task: str,
    token: str,
    dry_run: bool,
    json: bool,
    text: str,
    kind: str | None,
) -> None:
    finish(
        tasks.note(resolve_root(root), log, stage, task, text, kind, token, dry_run),
        json,
    )


@task.command("rewrite")
@options(ROOT, LOG, STAGE, TASK, TOKEN, DRY_RUN, JSON, TEXT, DECISION)
def rewrite(
    root: str | None,
    log: str,
    stage: str,
    task: str,
    token: str,
    dry_run: bool,
    json: bool,
    text: str,
    decision: str,
) -> None:
    finish(
        tasks.rewrite(
            resolve_root(root), log, stage, task, text, decision, token, dry_run
        ),
        json,
    )


@task.command("resolve")
@options(
    ROOT,
    LOG,
    STAGE,
    TASK,
    TOKEN,
    DRY_RUN,
    JSON,
    DECISION,
    click.option(
        "--as",
        "disposition",
        required=True,
        type=click.Choice(["human-cancelled", "not-applicable"]),
    ),
    click.option("--note", required=True),
)
def resolve(
    root: str | None,
    log: str,
    stage: str,
    task: str,
    token: str,
    dry_run: bool,
    json: bool,
    decision: str,
    disposition: str,
    note: str,
) -> None:
    finish(
        tasks.resolve(
            resolve_root(root),
            log,
            stage,
            task,
            disposition,
            decision,
            note,
            token,
            dry_run,
        ),
        json,
    )
