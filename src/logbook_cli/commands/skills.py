"""Skill catalog command group."""

import click

from logbook_cli.commands.common import (
    DRY_RUN,
    JSON,
    PROJECTS,
    ROOT,
    finish,
    options,
    resolve_root,
)
from logbook_cli.services import skills as service


@click.group(
    invoke_without_command=True, help="List and maintain the optional skill catalog."
)
@options(ROOT, JSON, click.option("--action"))
@click.pass_context
def skills(
    ctx: click.Context, root: str | None, json: bool, action: str | None
) -> None:
    if ctx.invoked_subcommand is None:
        finish(service.list_skills(resolve_root(root), action), json, "skills")


@skills.command("add")
@options(
    ROOT,
    JSON,
    DRY_RUN,
    click.option("--name", required=True),
    click.option("--scope", required=True),
    click.option("--chain", required=True, multiple=True),
    click.option("--action", multiple=True),
    click.option("--companion", multiple=True),
    click.option("--description"),
)
def add(
    root: str | None,
    json: bool,
    dry_run: bool,
    name: str,
    scope: str,
    chain: tuple[str, ...],
    action: tuple[str, ...],
    companion: tuple[str, ...],
    description: str | None,
) -> None:
    finish(
        service.add(
            resolve_root(root),
            name,
            scope,
            chain,
            action,
            companion,
            description,
            dry_run,
        ),
        True,
    )


@skills.command("extract")
@options(ROOT, JSON, PROJECTS)
def extract(root: str | None, json: bool, projects_dir: str) -> None:
    finish(service.extract(resolve_root(root), projects_dir), json, "extract")


@skills.command(
    "usage",
    help="Read Claude/Codex session history, including paths outside --root; report only repository/logbook work directories.",
)
@options(ROOT, JSON, PROJECTS, click.option("--since"))
def usage(root: str | None, json: bool, projects_dir: str, since: str | None) -> None:
    finish(service.history(resolve_root(root), projects_dir, since), json, "usage")
