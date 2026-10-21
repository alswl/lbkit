"""Read and safely update collaboration logbooks."""

from __future__ import annotations

import sys
from importlib.metadata import version
from pathlib import Path

import click

from logbook_cli.commands import domains, tasks, workflows
from logbook_cli.commands.common import ROOT
from logbook_cli.document import EXIT_PATH, LbError


@click.group(
    context_settings={"help_option_names": ["-h", "--help"]},
    invoke_without_command=True,
)
@ROOT
@click.version_option(
    (Path(__file__).resolve().parents[2] / "VERSION").read_text().strip()
    if (Path(__file__).resolve().parents[2] / "VERSION").is_file()
    else version("lbkit").replace(".dev0", "-dev"),
    message="%(version)s",
)
@click.pass_context
def app(ctx: click.Context, root: str | None) -> None:
    """Read and safely update collaboration logbooks."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


app.add_command(tasks.task)
app.add_command(workflows.workflow)
domains.register(app)


def main(argv: list[str] | None = None) -> int:
    try:
        result = app.main(args=argv, prog_name="lb", standalone_mode=False)
        return result if isinstance(result, int) else 0
    except click.ClickException as exc:
        exc.show()
        return exc.exit_code
    except click.Abort:
        print("lb: aborted", file=sys.stderr)
        return 1
    except LbError as exc:
        print(f"lb: {exc.message}", file=sys.stderr)
        return exc.code
    except OSError as exc:
        print(f"lb: I/O error: {exc}", file=sys.stderr)
        return EXIT_PATH


if __name__ == "__main__":
    raise SystemExit(main())
