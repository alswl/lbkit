"""Shared Click options and output dispatch."""

import click

from logbook_cli.render import render
from logbook_cli.services.common import Result

ROOT = click.option(
    "--root",
    default=None,
    metavar="DIR",
    help="Repository root (default: current directory).",
)
JSON = click.option("--json", is_flag=True, help="Emit machine-readable JSON.")
PROJECTS = click.option(
    "--projects-dir",
    default="projects",
    metavar="PATH",
    help="Project collection relative to --root.",
)
LOG = click.argument("log")
DRY_RUN = click.option("--dry-run", is_flag=True, help="Preview without writing.")
TOKEN = click.option(
    "--expect-version",
    "token",
    required=True,
    help="version_token of the file being changed.",
)
STAGE = click.option(
    "--stage", required=True, help="Exact stage title without status marker."
)
TASK = click.option("--task", required=True, help="Exact task text.")
TEXT = click.option("--text", required=True, help="One-line text.")
DECISION = click.option(
    "--decision", required=True, help="Source of the human decision."
)


def options(*decorators):
    def apply(function):
        for decorator in reversed(decorators):
            function = decorator(function)
        return function

    return apply


def resolve_root(root: str | None) -> str:
    if root is not None:
        return root
    ctx = click.get_current_context().parent
    while ctx is not None:
        if ctx.params.get("root") is not None:
            return ctx.params["root"]
        ctx = ctx.parent
    return "."


def finish(result: Result, json: bool, view: str = "default") -> None:
    render(result, json, view)
    if result.code:
        raise click.exceptions.Exit(result.code)
