"""Skill extraction and observed session-history commands."""

import click

from logbook_cli.commands.common import (
    JSON,
    PROJECTS,
    ROOT,
    finish,
    options,
    resolve_root,
)
from logbook_cli.services import skills as service


@click.command("extract")
@options(ROOT, JSON, PROJECTS)
def extract(root: str | None, json: bool, projects_dir: str) -> None:
    finish(service.extract(resolve_root(root), projects_dir), json, "extract")


@click.command(
    "history",
    help="Read Claude/Codex session history, including paths outside --root; report only repository/logbook work directories.",
)
@options(ROOT, JSON, PROJECTS, click.option("--since"), click.option("--machine"))
def usage(
    root: str | None,
    json: bool,
    projects_dir: str,
    since: str | None,
    machine: str | None,
) -> None:
    finish(
        service.history(resolve_root(root), projects_dir, since, machine), json, "usage"
    )
