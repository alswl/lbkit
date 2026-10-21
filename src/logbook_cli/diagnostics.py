"""Read-only toolkit diagnostics."""

import json
from pathlib import Path

import click

from logbook_cli import configuration as cfg
from logbook_cli.adapters import herdr
from logbook_cli.document import LbError


def config_check(root):
    try:
        cfg.read(root)
        cfg.read(root, cfg.SKILLS_NAME)
        return {
            "path": str(root / cfg.NAME),
            "valid": True,
            "issues": [],
            "coverage": "configuration only; runtime readiness not checked",
        }
    except (LbError, OSError) as exc:
        return {"path": str(root / cfg.NAME), "valid": False, "issues": [str(exc)]}


@click.group()
def app():
    """Inspect local configuration validity and adapter capabilities."""


@app.command()
@click.option("--repo", type=click.Path(path_type=Path), default=".")
@click.option("--json", "as_json", is_flag=True)
def doctor(repo, as_json):
    value = config_check(repo)
    click.echo(json.dumps({"config": value, "runtime": herdr.available()}, indent=2))
    if not value["valid"]:
        raise click.exceptions.Exit(1)


@app.group()
def adapter():
    """Inspect runtime adapter availability without controlling sessions."""


@adapter.command("list")
@click.option("--json", "as_json", is_flag=True)
def adapter_list(as_json):
    click.echo(json.dumps(herdr.available(), indent=2))


@adapter.command("check")
@click.argument("name", type=click.Choice(["herdr"]))
@click.option("--json", "as_json", is_flag=True)
def adapter_check(name, as_json):
    result = herdr.available()
    click.echo(json.dumps(result, indent=2))
    if not result["installed"] or not result["caller_managed"]:
        raise click.exceptions.Exit(1)


def main(argv=None):
    try:
        result = app.main(args=argv, prog_name="lbkit", standalone_mode=False)
        return result if isinstance(result, int) else 0
    except click.ClickException as exc:
        exc.show()
        return exc.exit_code
    except (LbError, OSError, ValueError) as exc:
        click.echo(f"lbkit: {exc}", err=True)
        return 4
