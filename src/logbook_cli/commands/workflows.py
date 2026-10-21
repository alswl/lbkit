"""Workflow template CLI."""

import click

from logbook_cli.commands.common import (
    DRY_RUN,
    JSON,
    LOG,
    ROOT,
    TOKEN,
    finish,
    options,
    resolve_root,
)
from logbook_cli.services import workflows as service
from logbook_cli.services.common import Result


@click.group()
@ROOT
def workflow(root):
    """Inspect, check and fill approved workflow templates."""


@workflow.command("list")
@options(ROOT, JSON)
def list_workflows(root, json):
    finish(service.catalog(resolve_root(root)), json)


@workflow.command("show")
@options(ROOT, click.argument("name"), JSON)
def show(root, name, json):
    finish(Result(service.inspect(resolve_root(root), name)), json)


@workflow.command("check")
@options(ROOT, click.argument("name"), JSON)
def check(root, name, json):
    info = service.inspect(resolve_root(root), name)
    finish(Result(info, 0 if info["contract_valid"] else 1), json)


@workflow.command("render")
@options(
    ROOT,
    click.argument("name"),
    click.option("--input-file", "inputs", required=True, metavar="FILE"),
    TOKEN,
    JSON,
)
def render(root, name, inputs, token, json):
    finish(service.render(resolve_root(root), name, inputs, token), json)


@workflow.command("diff")
@options(ROOT, LOG, JSON)
def difference(root, log, json):
    finish(service.difference(resolve_root(root), log), json)


@workflow.command("update")
@options(
    ROOT,
    click.argument("name"),
    click.option("--content-file", required=True),
    TOKEN,
    DRY_RUN,
    JSON,
)
def replace(root, name, content_file, token, dry_run, json):
    """Replace one authorized template from a complete reviewed candidate."""
    finish(
        service.replace_template(
            resolve_root(root), name, content_file, token, dry_run
        ),
        json,
    )


@workflow.command("create")
@options(
    ROOT,
    click.argument("name"),
    click.option("--content-file", required=True),
    DRY_RUN,
    JSON,
)
def create(root, name, content_file, dry_run, json):
    """Create one template in an existing approved workflow docs directory."""
    finish(
        service.create_template(resolve_root(root), name, content_file, dry_run), json
    )
