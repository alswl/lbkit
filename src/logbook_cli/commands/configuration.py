"""Atomic lb config commands for lbkit.yaml and lbkit-skills.yaml."""

import json
from pathlib import Path

import click

from logbook_cli import configuration as cfg
from logbook_cli.commands.common import (
    DRY_RUN,
    JSON,
    ROOT,
    TOKEN,
    options,
    resolve_root,
)
from logbook_cli.document import LbError, safe_path

INPUT = click.option(
    "--input-file", required=True, help="YAML/JSON mapping under the repository root."
)


def emit(value):
    click.echo(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def payload(root, filename):
    return cfg.decode(safe_path(root.resolve(), filename).read_bytes())


@click.group(
    help="Read, resolve and maintain lbkit.yaml and lbkit-skills.yaml; never execute an agent."
)
def config():
    pass


@config.command("show")
@options(ROOT, JSON)
def show(root, json):
    emit(cfg.snapshot(Path(resolve_root(root)).resolve()))


@config.command("check")
@options(ROOT, JSON)
def check(root, json):
    base = Path(resolve_root(root)).resolve()
    try:
        cfg.read(base)
        cfg.read(base, cfg.SKILLS_NAME)
        result = {"valid": True, "issues": [], "readiness": "not_checked"}
    except (LbError, OSError, ValueError) as exc:
        result = {"valid": False, "issues": [str(exc)], "readiness": "not_checked"}
    emit(result)
    if not result["valid"]:
        raise click.exceptions.Exit(4)


@config.command("resolve")
@options(
    ROOT,
    JSON,
    click.option("--agent"),
    click.option("--input-file", help="Ephemeral settings overrides; no writes."),
)
def resolve(root, json, agent, input_file):
    base = Path(resolve_root(root)).resolve()
    emit(cfg.resolve(base, agent, payload(base, input_file) if input_file else None))


def registry(name, group):
    @config.group(
        name=name,
        help=f"Manage {group} in {cfg.GROUPS[group]}. New objects start as draft; available means approved, not ready.",
    )
    def command():
        pass

    @command.command("list")
    @options(
        ROOT, JSON, click.option("--status", type=click.Choice(list(cfg.TRANSITIONS)))
    )
    def listing(root, json, status):
        _, data, value = cfg.read(Path(resolve_root(root)).resolve(), cfg.GROUPS[group])
        emit(
            {
                "version_token": cfg.token_of(data),
                group: {
                    k: v
                    for k, v in value[group].items()
                    if not status or v["status"] == status
                },
            }
        )

    @command.command("show")
    @options(click.argument("identity"), ROOT, JSON)
    def showing(identity, root, json):
        _, data, value = cfg.read(Path(resolve_root(root)).resolve(), cfg.GROUPS[group])
        if identity not in value[group]:
            cfg.refuse(f"unknown {group} ID: {identity}")
        emit(
            {
                "id": identity,
                "version_token": cfg.token_of(data),
                "object_digest": cfg.object_digest(value[group][identity]),
                "object": value[group][identity],
            }
        )

    def mutation(operation):
        decorators = [click.argument("identity"), ROOT, JSON, TOKEN, DRY_RUN]
        if operation != "remove":
            decorators.append(INPUT)

        @command.command(
            operation,
            help=f"{operation} one object. Input is a field patch; set-status accepts only status.",
        )
        @options(*decorators)
        def run(identity, root, json, token, dry_run, input_file=None):
            base = Path(resolve_root(root)).resolve()
            emit(
                cfg.mutate(
                    base,
                    group,
                    operation,
                    identity,
                    payload(base, input_file) if input_file else {},
                    token,
                    dry_run,
                )
            )

    for operation in ("create", "update", "set-status", "remove"):
        mutation(operation)
    return command


registry("agent", "agents")
registry("recipe", "recipes")


@config.command(
    "update", help="Patch the single settings object; omitted fields are preserved."
)
@options(ROOT, JSON, INPUT, TOKEN, DRY_RUN)
def update_settings(root, json, input_file, token, dry_run):
    import copy

    base = Path(resolve_root(root)).resolve()
    path, before, value = cfg.read(base)
    patch = payload(base, input_file)
    if set(patch) != {"settings"}:
        cfg.refuse("config update input must contain only settings")
    # Resolve validates references and nested overrides without starting anything.
    effective = cfg.resolve(base, overrides=patch)["settings"]
    updated = copy.deepcopy(value)
    updated["settings"] = effective
    cfg.validate(updated)
    emit(cfg.write_existing(path, before, cfg.encode(updated), token, dry_run))
