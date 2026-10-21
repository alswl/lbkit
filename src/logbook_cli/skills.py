"""Extract planned skill chains not covered by available work-type recipes."""

from __future__ import annotations

from pathlib import Path

from logbook_cli.document import (
    discover,
    parse,
)
from logbook_cli.format import PACKAGE_RE, QUOTE_RE, skill_chain
from logbook_cli.models import Field


def load(root: Path) -> list[dict]:
    from logbook_cli.configuration import SKILLS_NAME, read
    return list(read(root, SKILLS_NAME)[2]['recipes'].values())


def work_packages(root: Path, logbook: Path) -> list[tuple[str, list[str]]]:
    """Source records that name the todos they serve, from the project's sources/."""
    sources = logbook.parent.parent / "sources"
    found = []
    for path in sorted(sources.glob("*.md")) if sources.is_dir() else []:
        lines = path.read_text(encoding="utf-8").splitlines()[:8]
        quotes = [
            next(part for part in q if part).rstrip("…").strip()
            for line in lines
            if PACKAGE_RE.search(line)
            for q in QUOTE_RE.findall(line)
        ]
        if quotes:
            found.append((str(path.relative_to(root)), quotes))
    return found


def extract(root: Path, projects_dir: str) -> list[dict]:
    """Raw candidates: each 技能： sub-line with its todo and work packages.

    Deliberately no interpretation: the curating agent reads the linked work
    packages to find what was actually used and under which conditions.
    """
    covered = [
        set(e["steps"]) | {c["skill"] for c in e.get("companions", [])}
        for e in load(root) if e["status"] == "available"
    ]
    found = []
    for path in discover(root, projects_dir):
        doc = parse(path, root)
        packages = work_packages(root, path)
        for stage in doc.stages:
            for task in stage.tasks:
                # Actionless tasks remain valid; recipe curation still requires a work type.
                if task.action is None:
                    continue
                for annotation in task.annotations:
                    if annotation.kind is not Field.SKILLS:
                        continue
                    chain = skill_chain(annotation.value)
                    if chain.names and any(
                        set(chain.names) <= names for names in covered
                    ):
                        continue
                    found.append(
                        {
                            "action": task.action,
                            "chain": list(chain.names),
                            "raw": chain.raw,
                            "task": task.text,
                            "done": task.settled and task.state == "x",
                            "source": f"{path.relative_to(root)}:{annotation.line}",
                            "work_packages": [
                                p
                                for p, quotes in packages
                                if any(task.text.startswith(q) for q in quotes)
                            ],
                            "diagnostics": list(chain.diagnostics),
                        }
                    )
    return found
