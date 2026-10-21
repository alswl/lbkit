"""Run events and close-out views."""

import click

from logbook_cli.commands.common import (
    DRY_RUN,
    JSON,
    LOG,
    ROOT,
    finish,
    options,
    resolve_root,
)
from logbook_cli.services import closeout as service

THINKING = click.option(
    "--thinking", help="Adapter-resolved bound Thinking path inside root."
)
RUN_ID = click.option("--run-id")
SCOPE = click.option("--scope", default="logbook", help="logbook or exact Stage title.")


@click.group()
@ROOT
def run(root):
    """Record coordination events in bound Thinking."""


@run.command("record")
@options(
    ROOT,
    LOG,
    click.option("--thinking", required=True),
    click.option("--input-file", "event_file", required=True, metavar="FILE"),
    click.option("--expect-version", "thinking_token", required=True),
    DRY_RUN,
    JSON,
)
def record(root, log, thinking, event_file, thinking_token, dry_run, json):
    finish(
        service.record_event(
            resolve_root(root), log, thinking, event_file, thinking_token, dry_run
        ),
        json,
    )
