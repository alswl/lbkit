"""Skill extraction and observed session-history use cases."""

from logbook_cli import skills, usage
from logbook_cli.document import root_path
from logbook_cli.services.common import Result


def extract(root: str, projects_dir: str) -> Result:
    return Result({"candidates": skills.extract(root_path(root), projects_dir)})


def history(
    root: str, projects_dir: str, since: str | None, machine: str | None = None
) -> Result:
    return Result(
        {"events": usage.usage(root_path(root), projects_dir, since or "", machine)}
    )
