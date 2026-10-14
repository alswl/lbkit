"""Skill catalog use cases."""

from logbook_cli import skills, usage
from logbook_cli.document import root_path
from logbook_cli.services.common import Result


def list_skills(root: str, action: str | None) -> Result:
    entries = skills.load(root_path(root))
    return Result(
        {
            "skills": [e for e in entries if action in e.get("actions", [])]
            if action
            else entries
        }
    )


def add(
    root: str,
    name: str,
    scope: str,
    chain: tuple[str, ...],
    action: tuple[str, ...],
    companion: tuple[str, ...],
    description: str | None,
    dry_run: bool,
) -> Result:
    entry = {
        "name": name,
        "scope": scope,
        "chain": list(chain),
        "actions": list(action),
        "companions": [
            {"skill": skill.strip(), "when": when.strip()}
            for skill, _, when in (c.partition("=") for c in companion)
        ],
        "description": description or "",
    }
    return Result(
        {
            "path": skills.CATALOG,
            "dry_run": dry_run,
            "added": skills.add(root_path(root), entry, dry_run),
        }
    )


def extract(root: str, projects_dir: str) -> Result:
    return Result({"candidates": skills.extract(root_path(root), projects_dir)})


def history(
    root: str, projects_dir: str, since: str | None, machine: str | None = None
) -> Result:
    return Result(
        {"events": usage.usage(root_path(root), projects_dir, since or "", machine)}
    )
