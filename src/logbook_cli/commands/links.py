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


@link.command(
    "verify", help="Register an offline observation of one existing external link."
)
@options(
    ROOT,
    LOG,
    TOKEN,
    DRY_RUN,
    JSON,
    click.option("--line", type=click.IntRange(min=1), required=True),
    click.option("--target", required=True),
    click.option("--label", required=True),
    click.option("--observed-at", required=True),
    click.option("--observer", required=True),
    click.option("--basis", required=True),
    click.option(
        "--outcome",
        type=click.Choice(["verified", "unavailable", "revoked"]),
        default="verified",
    ),
    click.option("--bind-stage"),
    click.option("--bind-task"),
    click.option("--result-identity"),
)
def verify(
    root: str | None,
    log: str,
    token: str,
    dry_run: bool,
    json: bool,
    line: int,
    target: str,
    label: str,
    observed_at: str,
    observer: str,
    basis: str,
    outcome: str,
    bind_stage: str | None,
    bind_task: str | None,
    result_identity: str | None,
) -> None:
    finish(
        links.verify(
            resolve_root(root),
            log,
            line,
            target,
            label,
            observed_at,
            observer,
            basis,
            outcome,
            token,
            dry_run,
            bind_stage,
            bind_task,
            result_identity,
        ),
        json,
    )
