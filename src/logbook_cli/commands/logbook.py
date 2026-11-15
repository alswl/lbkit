"""Top-level logbook commands."""

import click

from logbook_cli.commands.common import (
    DOCUMENT_TOKEN as TOKEN,
)
from logbook_cli.commands.common import (
    DRY_RUN,
    JSON,
    LOG,
    PROJECTS,
    ROOT,
    finish,
    options,
    resolve_root,
)
from logbook_cli.services import logbook


@click.command("list", help="List project logbooks.")
@options(ROOT, PROJECTS, JSON)
def list_logs(root: str | None, projects_dir: str, json: bool) -> None:
    finish(logbook.list_logs(resolve_root(root), projects_dir), json, "list")


@click.command("context", help="Show context and the version token.")
@options(ROOT, LOG, JSON)
def context(root: str | None, log: str, json: bool) -> None:
    finish(logbook.inspect(resolve_root(root), log), json)


@click.command("check", help="Check one logbook or all project logbooks.")
@options(
    ROOT,
    PROJECTS,
    click.argument("log", required=False),
    click.option("--all", is_flag=True),
    JSON,
)
def check(
    root: str | None, projects_dir: str, log: str | None, all: bool, json: bool
) -> None:
    finish(logbook.validate(resolve_root(root), log, all, projects_dir), json, "check")


@click.command("state", help="Show structured state and derived summary.")
@options(ROOT, LOG, JSON)
def state(root: str | None, log: str, json: bool) -> None:
    finish(logbook.inspect(resolve_root(root), log, "state"), json)


@click.command("sync", help="Synchronize stage markers and owned status summaries.")
@options(ROOT, LOG, TOKEN, DRY_RUN, JSON)
def sync(root: str | None, log: str, token: str, dry_run: bool, json: bool) -> None:
    finish(logbook.sync(resolve_root(root), log, token, dry_run), json)


@click.command(
    "state-set", help="Record lifecycle and generate its compact status line."
)
@options(
    ROOT,
    LOG,
    TOKEN,
    DRY_RUN,
    JSON,
    click.option(
        "--lifecycle",
        type=click.Choice(
            ["draft", "ready", "active", "paused", "completed", "terminated"]
        ),
        required=True,
    ),
    click.option("--basis", required=True),
)
def state_set(root, log, token, dry_run, json, lifecycle, basis):
    from logbook_cli.lifecycle import set_state

    finish(set_state(resolve_root(root), log, lifecycle, basis, token, dry_run), json)


@click.command(
    "recover", help="Preview or finish an interrupted document/state transaction."
)
@options(ROOT, LOG, DRY_RUN, JSON, click.option("--expect-version"))
def recover(root, log, dry_run, json, expect_version):
    from pathlib import Path

    from logbook_cli.document import LbError, root_path
    from logbook_cli.services.common import Result
    from logbook_cli.storage import recover as recover_state

    base = root_path(resolve_root(root))
    raw = Path(log)
    path = raw if raw.is_absolute() else base / raw
    if path.is_symlink() or not path.resolve().is_relative_to(base):
        raise LbError("recovery path must be inside root and not a symlink")
    finish(Result(recover_state(base, path.resolve(), expect_version, dry_run)), json)


def register(app: click.Group) -> None:
    for command in (
        list_logs,
        context,
        check,
        state,
        sync,
        state_set,
        recover,
        init_state,
        sync_state,
    ):
        app.add_command(command)


@click.command("init-state", help="Initialize an explicitly associated new run.")
@options(
    ROOT,
    LOG,
    click.option("--name", required=True),
    click.option("--document", multiple=True),
    DRY_RUN,
    JSON,
)
def init_state(root, log, name, document, dry_run, json):
    from logbook_cli import unified
    from logbook_cli.document import root_path, safe_path
    from logbook_cli.services.common import Result

    base = root_path(resolve_root(root))
    finish(
        Result(unified.initialize(base, safe_path(base, log), name, document, dry_run)),
        json,
    )


@click.command("sync-state", help="Explicitly project Markdown into unified run state.")
@options(ROOT, LOG, DRY_RUN, JSON)
def sync_state(root, log, dry_run, json):
    from logbook_cli.repository import sync_document
    from logbook_cli.services.common import Result

    finish(Result(sync_document(resolve_root(root), log, dry_run)), json)
