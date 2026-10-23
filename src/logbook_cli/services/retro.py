"""Incremental main-branch discovery and a host-owned feedback ledger."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess

from logbook_cli import records
from logbook_cli.document import (
    EXIT_REFUSED,
    EXIT_USAGE,
    LbError,
    require_token,
    root_path,
    safe_path,
)
from logbook_cli.services.common import Result, load, save


def git(root, *args):
    result = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, timeout=30
    )
    if result.returncode:
        raise LbError(
            "Git snapshot unavailable: " + result.stderr.strip(), EXIT_REFUSED
        )
    return result.stdout


def scan(root, since, ref, ledger=None):
    base = root_path(root)
    if ref.startswith("-") or "\n" in ref:
        raise LbError("invalid ref", EXIT_USAGE)
    revision = git(base, "rev-parse", "--verify", ref + "^{commit}").strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", since):
        raise LbError("--since must be YYYY-MM-DD", EXIT_USAGE)
    names = git(
        base,
        "log",
        "--since=" + since,
        "--format=",
        "--name-only",
        revision,
        "--",
        "projects",
        "docs",
    ).splitlines()
    known = set()
    if ledger:
        for _, item in records.read(load(root, ledger), "retro"):
            known.update(item.get("source_ids", []))
    findings = []
    for path in sorted(set(names)):
        if not path.endswith(".md") or not (
            "/thinking/" in path
            or path in {"docs/skills-feedback.md", "docs/lbkit-feedback.md"}
        ):
            continue
        exists = subprocess.run(
            ["git", "-C", str(base), "cat-file", "-e", revision + ":" + path],
            capture_output=True,
        )
        if exists.returncode:
            continue
        text = git(base, "show", revision + ":" + path)
        heading = ""
        for number, line in enumerate(text.splitlines(), 1):
            if line.startswith("## "):
                heading = line[3:]
            if not line.strip() or not re.search(
                r"skill|技能|反馈|采纳|workflow|复盘", line, re.I
            ):
                continue
            if line.startswith("#"):
                continue
            identity = hashlib.sha256(
                (path + "\0" + heading + "\0" + line.strip()).encode()
            ).hexdigest()
            if identity not in known:
                findings.append(
                    {
                        "source_id": identity,
                        "path": path,
                        "line": number,
                        "heading": heading,
                        "excerpt": line[:500],
                        "revision": revision,
                    }
                )
    dirty = git(base, "status", "--porcelain", "--", "projects", "docs").splitlines()
    return Result(
        {
            "revision": revision,
            "ref": ref,
            "since": since,
            "findings": findings,
            "coverage": "committed snapshot; changed files may contain historical backfill; human semantic classification required",
            "uncommitted_excluded": dirty,
            "checkpoint_written": False,
            "branches_not_inspected": "other branches/worktrees and their unmerged returns are not inspected",
        }
    )


def validate(item):
    required = {
        "id",
        "summary",
        "classification",
        "owner",
        "source_ids",
        "sources",
        "disposition",
        "implementation",
        "adoption",
        "verification",
    }
    if not isinstance(item, dict) or set(item) != required:
        raise LbError(
            "retro record requires exactly: " + ", ".join(sorted(required)), EXIT_USAGE
        )
    for key in ("id", "summary", "classification", "owner"):
        records.single_line(item[key], key)
    if item["disposition"] not in {
        "proposed",
        "accepted",
        "deferred",
        "rejected",
    } or item["implementation"] not in {"not-started", "implemented", "verified"}:
        raise LbError("invalid retro disposition/implementation", EXIT_USAGE)
    for key in ("source_ids", "sources", "adoption", "verification"):
        if not isinstance(item[key], list) or not all(
            isinstance(v, str) and v.strip() for v in item[key]
        ):
            raise LbError(f"{key} must be an array of nonempty references", EXIT_USAGE)
    if not item["sources"] or not item["source_ids"]:
        raise LbError("retro finding needs attributable sources", EXIT_USAGE)
    if item["implementation"] == "verified" and not item["verification"]:
        raise LbError("verified finding needs behavior evidence", EXIT_REFUSED)
    return item


def show(root, ledger, identity):
    doc = load(root, ledger)
    items = [validate(r) for _, r in records.read(doc, "retro")]
    matches = [r for r in items if not identity or r["id"] == identity]
    if identity and len(matches) != 1:
        raise LbError("missing or duplicate retro ID", EXIT_REFUSED)
    return Result(
        {
            "path": str(doc.path.relative_to(doc.root)),
            "version_token": doc.token,
            "findings": matches,
        }
    )


def record(root, ledger, input_file, token, dry_run, update=False):
    doc = load(root, ledger)
    require_token(doc, token)
    records.read(doc, "retro", require_closed=True)
    # Writes are main-branch only; never checkout or discard another workspace.
    if git(doc.root, "branch", "--show-current").strip() != "master":
        raise LbError(
            "retro writes require the host master checkout; scan can read any pinned ref",
            EXIT_REFUSED,
        )
    try:
        item = validate(json.loads(safe_path(doc.root, input_file).read_text()))
    except (ValueError, TypeError) as exc:
        raise LbError(str(exc), EXIT_USAGE) from exc
    old = records.read(doc, "retro")
    matches = [(i, r) for i, r in old if r.get("id") == item["id"]]
    if len(matches) > 1 or (update and not matches):
        raise LbError("missing or duplicate retro ID", EXIT_REFUSED)
    if matches:
        _, previous = matches[0]
        if not update and previous != item:
            raise LbError("ID exists; use retro update", EXIT_REFUSED)
        if not set(previous["source_ids"]).issubset(item["source_ids"]):
            raise LbError("update cannot discard source identity", EXIT_REFUSED)
    changed = records.put(doc, "retro", item)

    def display(value):
        return f"- **{value['id']}** {value['summary']} · {value['disposition']} · {value['implementation']}"

    current_line = display(item)
    previous_line = display(matches[0][1]) if matches else None
    lines = changed.splitlines(keepends=True)
    locations = [
        i
        for i, line in enumerate(lines)
        if previous_line and line.rstrip("\r\n") == previous_line
    ]
    if len(locations) == 1:
        index = locations[0]
        ending = "\r\n" if lines[index].endswith("\r\n") else "\n"
        lines[index] = current_line + ending
        changed = "".join(lines)
    elif not matches or previous_line not in doc.text:
        nl = "\r\n" if b"\r\n" in doc.data else "\n"
        changed += nl + current_line + nl
    return save(doc, changed, dry_run, finding_id=item["id"])
