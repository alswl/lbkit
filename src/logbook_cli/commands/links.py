"""Link command group; business rules live in services.links."""

import click

from logbook_cli.commands.common import (
    DRY_RUN,
    JSON,
    LOG,
    ROOT,
    STAGE,
    TOKEN,
    finish,
    options,
    resolve_root,
)
from logbook_cli.services import links


@click.group(help="Maintain logbook links.")
@ROOT
def link(root: str | None) -> None:
    pass


@link.command("add")
@options(
    ROOT,
    LOG,
    STAGE,
    TOKEN,
    DRY_RUN,
    JSON,
    click.option("--link", "value", required=True, help="One Markdown link."),
)
def add(
    root: str | None,
    log: str,
    stage: str,
    token: str,
    dry_run: bool,
    json: bool,
    value: str,
) -> None:
    finish(links.add(resolve_root(root), log, stage, value, token, dry_run), json)


@link.command("rewrite")
@options(
    ROOT,
    LOG,
    TOKEN,
    DRY_RUN,
    JSON,
    click.option("--from", "old", required=True, help="Target prefix to replace."),
    click.option("--to", "new", required=True, help="Replacement prefix."),
)
def rewrite(
    root: str | None,
    log: str,
    token: str,
    dry_run: bool,
    json: bool,
    old: str,
    new: str,
) -> None:
    finish(links.rewrite(resolve_root(root), log, old, new, token, dry_run), json)
