"""Retrospective CLI; synthesis belongs to the skill."""

import click

from logbook_cli.commands.common import (
    DRY_RUN,
    JSON,
    ROOT,
    TOKEN,
    finish,
    options,
    resolve_root,
)
from logbook_cli.services import retro as service


@click.group()
@ROOT
def retro(root):
    """Review a fixed main-branch snapshot and track feedback adoption."""


@retro.command("scan")
@options(
    ROOT,
    click.option("--since", required=True),
    click.option("--ref", default="master"),
    click.option("--ledger"),
    JSON,
)
def scan(root, since, ref, ledger, json):
    finish(service.scan(resolve_root(root), since, ref, ledger), json)


@retro.command("show")
@options(
    ROOT,
    click.option("--ledger", required=True),
    click.option("--id", "identity"),
    JSON,
)
def show(root, ledger, identity, json):
    finish(service.show(resolve_root(root), ledger, identity), json)


@retro.command("record")
@options(
    ROOT,
    click.option("--ledger", required=True),
    click.option("--input-file", "input_file", required=True, metavar="FILE"),
    TOKEN,
    DRY_RUN,
    JSON,
)
def record(root, ledger, input_file, token, dry_run, json):
    finish(service.record(resolve_root(root), ledger, input_file, token, dry_run), json)


@retro.command("update")
@options(
    ROOT,
    click.option("--ledger", required=True),
    click.option("--input-file", "input_file", required=True, metavar="FILE"),
    TOKEN,
    DRY_RUN,
    JSON,
)
def update(root, ledger, input_file, token, dry_run, json):
    finish(
        service.record(resolve_root(root), ledger, input_file, token, dry_run, True),
        json,
    )
