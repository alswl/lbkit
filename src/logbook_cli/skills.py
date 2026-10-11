"""Optional per-repository skill list: kinds of work and the skill chains they use."""

from __future__ import annotations

import json
from pathlib import Path

from logbook_cli.document import (
    EXIT_PATH,
    EXIT_REFUSED,
    LbError,
    discover,
    parse,
)
from logbook_cli.format import PACKAGE_RE, QUOTE_RE, skill_chain
from logbook_cli.models import Field

CATALOG = "lbkit-skills.json"
SCHEMA_REF = ".lbkit/schemas/lbkit-skills.schema.json"
VERSIONS = ("0.1.0",)
FIELDS = {"name", "scope", "chain", "actions", "companions", "description"}
REQUIRED = ("name", "scope")


def catalog_path(root: Path) -> Path:
    return root / CATALOG


def validate(data: object) -> list[dict]:
    if not isinstance(data, dict) or set(data) - {"$schema", "version", "skills"}:
        raise LbError(
            f'{CATALOG}: top level must be {{"version": ..., "skills": [...]}}',
            EXIT_PATH,
        )
    if data.get("version") not in VERSIONS:
        raise LbError(
            f"{CATALOG}: unsupported version {data.get('version')!r}; "
            f"supported: {', '.join(VERSIONS)}",
            EXIT_PATH,
        )
    if not isinstance(data.get("$schema", ""), str):
        raise LbError(f"{CATALOG}: $schema must be a string", EXIT_PATH)
    entries = data.get("skills", [])
    if not isinstance(entries, list):
        raise LbError(f"{CATALOG}: skills must be an array", EXIT_PATH)
    seen = set()
    for number, entry in enumerate(entries, 1):
        where = f"{CATALOG}: skills #{number}"
        if not isinstance(entry, dict):
            raise LbError(f"{where}: must be an object", EXIT_PATH)
        if set(entry) - FIELDS:
            raise LbError(
                f"{where}: unknown fields {sorted(set(entry) - FIELDS)}", EXIT_PATH
            )
        for field in REQUIRED:
            value = entry.get(field)
            if not isinstance(value, str) or not value.strip():
                raise LbError(f"{where}: {field} must be a non-empty string", EXIT_PATH)
        chain, actions = entry.get("chain"), entry.get("actions", [])
        if not (
            isinstance(chain, list)
            and chain
            and all(isinstance(s, str) and s.strip() for s in chain)
        ):
            raise LbError(f"{where}: chain must be a non-empty string array", EXIT_PATH)
        if not (isinstance(actions, list) and all(isinstance(a, str) for a in actions)):
            raise LbError(f"{where}: actions must be a string array", EXIT_PATH)
        companions = entry.get("companions", [])
        if not (
            isinstance(companions, list)
            and all(
                isinstance(c, dict)
                and set(c) == {"skill", "when"}
                and all(isinstance(v, str) and v.strip() for v in c.values())
                for c in companions
            )
        ):
            raise LbError(
                f"{where}: companions must be objects with skill and when", EXIT_PATH
            )
        if not isinstance(entry.get("description", ""), str):
            raise LbError(f"{where}: description must be a string", EXIT_PATH)
        if entry["name"] in seen:
            raise LbError(f"{where}: duplicate name {entry['name']!r}", EXIT_PATH)
        seen.add(entry["name"])
    return entries


def read_document(root: Path) -> dict:
    path = catalog_path(root)
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise LbError(f"{CATALOG} must be a regular file", EXIT_PATH)
    if not path.exists():
        return {"$schema": SCHEMA_REF, "version": VERSIONS[-1], "skills": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise LbError(f"{CATALOG}: invalid JSON: {exc}", EXIT_PATH) from exc


def load(root: Path) -> list[dict]:
    return validate(read_document(root))


def dump(value: object, indent: int = 0) -> str:
    """Prettier-like JSON: objects expanded, arrays of scalars on one line."""
    pad, inner = " " * indent, " " * (indent + 2)
    if isinstance(value, dict):
        items = [
            f"{inner}{json.dumps(k, ensure_ascii=False)}: {dump(v, indent + 2)}"
            for k, v in value.items()
        ]
        return "{\n" + ",\n".join(items) + f"\n{pad}}}" if items else "{}"
    if isinstance(value, list) and any(isinstance(v, (dict, list)) for v in value):
        items = [f"{inner}{dump(v, indent + 2)}" for v in value]
        return "[\n" + ",\n".join(items) + f"\n{pad}]"
    return json.dumps(value, ensure_ascii=False)


def add(root: Path, entry: dict, dry_run: bool) -> dict:
    document = read_document(root)
    entries = validate(document)
    if any(e["name"] == entry["name"] for e in entries):
        raise LbError(f"already listed: {entry['name']}", EXIT_REFUSED)
    entry = {k: v for k, v in entry.items() if v}
    document = {**document, "skills": [*entries, entry]}
    validate(document)
    if not dry_run:
        catalog_path(root).write_text(dump(document) + "\n", encoding="utf-8")
    return entry


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
        set(e["chain"]) | {c["skill"] for c in e.get("companions", [])}
        for e in load(root)
    ]
    found = []
    for path in discover(root, projects_dir):
        doc = parse(path, root)
        packages = work_packages(root, path)
        for stage in doc.stages:
            for task in stage.tasks:
                # Actionless tasks remain valid; catalog curation still requires a work type.
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
