"""Object-oriented command routes with atomic service operations."""

import click

from logbook_cli.commands import (
    configuration,
    links,
    logbook,
    retro,
    run,
    skills,
    tasks,
    workflows,
)
from logbook_cli.commands.common import (
    DRY_RUN,
    JSON,
    LOG,
    ROOT,
    STAGE,
    TASK,
    TOKEN,
    finish,
    options,
    resolve_root,
)
from logbook_cli.services import (
    agent_observation,
    agent_wait,
    agents,
    dispatches,
    execution,
    skill_capabilities,
    task_lifecycle,
)
from logbook_cli.services import workflows as workflow_service
from logbook_cli.services.common import Result

INPUT = click.option(
    "--input-file",
    required=True,
    metavar="FILE",
    help="JSON input file inside the repository root.",
)
BASIS = click.option(
    "--basis",
    required=True,
    help="Evidence or explicit decision authorizing this transition.",
)
THINKING = click.option(
    "--thinking",
    required=True,
    metavar="FILE",
    help="Bound Thinking file; --expect-version refers to this file.",
)
ID = click.argument("dispatch_id")


def route(group, name, service, *parameters, **fixed):
    """Adapt shared CLI options to a service without adding orchestration."""

    def callback(root, json, **kwargs):
        result = service(root=resolve_root(root), **kwargs, **fixed)
        finish(result if isinstance(result, Result) else Result(result), json)

    callback.__name__ = name.replace("-", "_")
    group.command(name)(options(ROOT, *parameters, JSON)(callback))


@click.group("log")
@ROOT
def log(root):
    """Inspect and maintain a logbook and its derived reports."""


logbook.register(log)
log.add_command(links.link, "links")
log.add_command(run.run, "events")


@log.command("create")
@options(
    ROOT,
    click.argument("output"),
    click.option("--from-workflow", "name", required=True),
    INPUT,
    TOKEN,
    DRY_RUN,
    JSON,
)
def create_log(root, output, name, input_file, token, dry_run, json):
    finish(
        workflow_service.instantiate(
            resolve_root(root), name, input_file, token, output, dry_run
        ),
        json,
    )


@log.command("report")
@options(
    ROOT,
    LOG,
    run.THINKING,
    run.RUN_ID,
    run.SCOPE,
    click.option(
        "--view", type=click.Choice(["closeout", "metrics"]), default="closeout"
    ),
    JSON,
)
def report(root, log, thinking, run_id, scope, view, json):
    from logbook_cli.services import closeout

    result = getattr(closeout, view)(resolve_root(root), log, thinking, run_id, scope)
    finish(result if isinstance(result, Result) else Result(result), json)


@click.group()
@ROOT
def dispatch(root):
    """Record delegation and execution attempts independently of acceptance."""


@click.group()
@ROOT
def agent(root):
    """Bind sessions, observe runtime, and perform guarded transport actions."""


@agent.group("observation")
@ROOT
def observation_commands(root):
    """Configure and recover durable worker observation."""


route(observation_commands, "context", agent_observation.context, LOG)
route(
    observation_commands,
    "configure",
    agent_observation.configure,
    LOG,
    INPUT,
    TOKEN,
    DRY_RUN,
)


@agent.group("event")
@ROOT
def event_commands(root):
    """Handle observed work independently of notification delivery."""


for action in ("defer", "resolve"):
    route(
        event_commands,
        action,
        agent_observation.event_action,
        LOG,
        click.argument("event_id"),
        click.option("--action-id", required=True),
        INPUT,
        TOKEN,
        DRY_RUN,
        action=action,
    )


@agent.group("answer")
@ROOT
def answer_commands(root):
    """Submit, reconcile or prepare a correlated Answer attempt."""


for name, mode in (("submit", "adapter"), ("prepare", "external")):
    route(
        answer_commands,
        name,
        agent_observation.answer_submit,
        LOG,
        click.argument("event_id"),
        click.option("--operation-id", required=True),
        INPUT,
        TOKEN,
        DRY_RUN,
        mode=mode,
    )
route(
    answer_commands,
    "reconcile",
    agent_observation.answer_reconcile,
    LOG,
    click.argument("operation_id"),
    click.option("--input-file"),
    TOKEN,
    DRY_RUN,
)


@agent.command("wait")
@options(
    ROOT,
    click.option("--input-file"),
    click.option("--log"),
    click.option("--expect-version", "token"),
    click.option("--stream", is_flag=True),
    DRY_RUN,
    click.option("--timeout", type=float, required=True),
    JSON,
)
def wait_command(root, input_file, log, token, stream, dry_run, timeout, json):
    result = agent_wait.wait(
        resolve_root(root), input_file, timeout, log, token, stream, dry_run
    )
    if stream and not dry_run:
        if result.code:
            raise click.exceptions.Exit(result.code)
    else:
        finish(result, json)


@click.group("skill")
@ROOT
def skill(root):
    """Inspect definitions, conservative readiness, and attributed usage."""


@click.group("execution")
def execution_commands():
    """Record attributed execution facts and inspect delegation constraints."""


log.add_command(execution_commands)
route(execution_commands, "context", execution.context, LOG)
route(execution_commands, "record", execution.record, LOG, INPUT, TOKEN, DRY_RUN)


def register(app):
    app.add_command(log)
    app.add_command(dispatch)
    app.add_command(agent)
    app.add_command(skill)
    app.add_command(configuration.config)
    skill.add_command(skills.extract, "extract")
    skill.add_command(skills.usage, "history")
    app.add_command(retro.retro, "feedback")
    route(
        tasks.task,
        "identify",
        task_lifecycle.identify,
        LOG,
        STAGE,
        TASK,
        click.option("--task-id"),
        TOKEN,
        DRY_RUN,
    )
    route(tasks.task, "show", task_lifecycle.show, LOG, click.argument("task_id"))
    route(tasks.task, "migrate", task_lifecycle.migrate, LOG, TOKEN, DRY_RUN)
    for action in ("complete", "pause", "resume", "block", "unblock"):
        route(
            tasks.task,
            action,
            task_lifecycle.semantic_transition,
            LOG,
            click.argument("task_id"),
            BASIS,
            TOKEN,
            DRY_RUN,
            click.option("--reason"),
            click.option("--to", type=click.Choice(["pending", "active"])),
            action=action,
        )
    for action in ("start", "record-result", "accept", "cancel", "reopen"):
        extra = (
            (INPUT,)
            if action == "record-result"
            else (click.option("--candidate", required=True),)
            if action == "accept"
            else ()
        )
        route(
            tasks.task,
            action,
            task_lifecycle.transition,
            LOG,
            click.argument("task_id"),
            BASIS,
            TOKEN,
            DRY_RUN,
            *extra,
            action=action,
        )
    route(dispatch, "list", dispatches.show, LOG, THINKING)
    route(dispatch, "show", dispatches.show, LOG, THINKING, ID)
    route(dispatch, "create", dispatches.create, LOG, THINKING, INPUT, TOKEN, DRY_RUN)
    route(
        dispatch,
        "set-status",
        dispatches.transition,
        LOG,
        THINKING,
        ID,
        click.option(
            "--status", required=True, type=click.Choice(list(dispatches.TRANSITIONS))
        ),
        BASIS,
        TOKEN,
        DRY_RUN,
    )
    route(
        dispatch,
        "attempt",
        dispatches.attempt,
        LOG,
        THINKING,
        ID,
        click.argument("attempt_id"),
        click.option(
            "--status",
            required=True,
            type=click.Choice(["started", "finished", "failed", "interrupted"]),
        ),
        BASIS,
        TOKEN,
        DRY_RUN,
    )
    route(agent, "open", agents.session_operation, INPUT, action="open")
    route(agent, "close-session", agents.session_operation, INPUT, action="close")
    route(agent, "bind", agents.bind, LOG, THINKING, ID, INPUT, TOKEN, DRY_RUN)
    route(
        agent,
        "inspect",
        agents.inspect,
        LOG,
        THINKING,
        ID,
        click.option("--live", is_flag=True),
    )
    for action in ("send", "close"):
        extra = (
            (
                click.option("--message-file", required=True, metavar="FILE"),
                click.option("--operation-id", required=True),
                click.option(
                    "--expect-execution-version", "execution_token", required=True
                ),
            )
            if action == "send"
            else ()
        )
        route(
            agent,
            action,
            agents.control,
            LOG,
            THINKING,
            ID,
            click.option("--expected-session", required=True),
            click.option("--expected-observation", required=True),
            *((BASIS,) if action == "close" else ()),
            TOKEN,
            DRY_RUN,
            *extra,
            action=action,
        )
    route(skill, "list", skill_capabilities.catalog)
    route(skill, "show", skill_capabilities.definition, click.argument("name"))
    route(
        skill,
        "check",
        skill_capabilities.readiness,
        click.argument("name"),
        click.option("--command", "commands", multiple=True),
    )
    route(skill, "usage", skill_capabilities.usage, LOG, THINKING)
    route(
        skill,
        "record-usage",
        skill_capabilities.record_usage,
        LOG,
        THINKING,
        click.option(
            "--input-file",
            required=True,
            metavar="FILE",
            help=(
                "One usage JSON object inside root: id, task_id, skill, state, "
                "outcome, basis, at. For several returns, record each separately "
                "using the returned Thinking token; arrays are not accepted."
            ),
        ),
        TOKEN,
        DRY_RUN,
    )
    route(
        workflows.workflow,
        "set-status",
        workflow_service.set_status,
        click.argument("name"),
        click.option(
            "--status",
            required=True,
            type=click.Choice(["draft", "available", "deprecated", "retired"]),
        ),
        BASIS,
        TOKEN,
        DRY_RUN,
    )
