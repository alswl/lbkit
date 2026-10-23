"""Template contract checks and deterministic fill-in, without replanning."""

from __future__ import annotations

import hashlib
import json
import re

from logbook_cli import records
from logbook_cli.document import (
    EXIT_REFUSED,
    EXIT_USAGE,
    LbError,
    check,
    parse_text,
    require_token,
    root_path,
    safe_path,
)
from logbook_cli.edit import ADVISORY_ISSUES
from logbook_cli.services.common import Result, load
from logbook_cli.state import encode
from logbook_cli.state import path_for as state_path_for
from logbook_cli.state import token as state_token
from logbook_cli.storage import write_bytes


def template(root, name):
    base = root_path(root)
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]*", name):
        raise LbError("workflow must be a simple directory name", EXIT_USAGE)
    directory = (base / "workflows" / name / "docs").resolve()
    if not directory.is_relative_to(base) or not directory.is_dir():
        raise LbError("workflow docs directory is missing or outside root")
    candidates = [
        p
        for p in directory.glob("*.md")
        if p.resolve().is_relative_to(base)
        and re.search(r"(?m)^## (?:Run-instance template|运行实例模板)", p.read_text())
    ]
    if len(candidates) != 1:
        raise LbError(
            "workflow must have exactly one run-instance template", EXIT_REFUSED
        )
    return load(root, str(candidates[0]))


def section(text):
    # Template examples contain H2s; the named rulings section is the delimiter.
    match = re.search(r"(?m)^## (?:Run-instance template|运行实例模板)[^\n]*\n", text)
    end = re.search(r"(?m)^## (?:Established rulings|既定裁定)[^\n]*", text)
    if not match or not end or end.start() <= match.end():
        raise LbError(
            "template and established rulings sections are required", EXIT_REFUSED
        )
    return text[match.end() : end.start()]


def inspect(root, name):
    return inspect_document(template(root, name), name)


def inspect_document(doc, name):
    body = section(doc.text)
    problems = []
    for slot in (1, 2, 3):
        if not re.search(rf"(?:Slot|槽)\s*{slot}", body):
            problems.append(f"missing slot {slot}")
    if "<DATE>" not in body:
        problems.append("missing target-date placeholder")
    if not re.search(r"(?m)^(?:Title:|标题：)", body):
        problems.append("missing title declaration")
    if not re.search(r"(?m)^- \[ \] ", body):
        problems.append("missing ordered todo manifest")
    if not re.search(r"(?m)^(?:Goal:|目标：)[ \t]*\S[^\n]*", body):
        problems.append("missing human goal template")
    return {
        "name": name,
        "status": lifecycle(doc),
        "path": str(doc.path.relative_to(doc.root)),
        "version_token": doc.token,
        "placeholders": sorted(set(re.findall(r"<[^<>\n]+>", body))),
        "issues": problems,
        "contract_valid": not problems,
        "coverage": "template markers only; render checks supported syntax; instantiate checks the output candidate; semantics belong to lb-workflow",
        "instance_validation": "unknown; requires actual run evidence",
    }


def catalog(root):
    base = root_path(root)
    directory = base / "workflows"
    rows = []
    if directory.is_dir() and directory.resolve().is_relative_to(base):
        for path in sorted(directory.iterdir()):
            if path.is_dir() and path.resolve().is_relative_to(base):
                try:
                    rows.append(inspect(root, path.name))
                except LbError as exc:
                    rows.append(
                        {
                            "name": path.name,
                            "contract_valid": False,
                            "issues": [exc.message],
                        }
                    )
    return Result({"workflows": rows})


def render(root, name, inputs_file, token):
    doc = template(root, name)
    if token != doc.token:
        raise LbError("template changed; reread workflow show", EXIT_REFUSED)
    info = inspect(root, name)
    if info["issues"]:
        raise LbError("invalid template: " + "; ".join(info["issues"]), EXIT_REFUSED)
    try:
        inputs = json.loads(safe_path(doc.root, inputs_file).read_text())
        if not isinstance(inputs, dict) or set(inputs) != {
            "date",
            "working_directories",
            "rulings",
        }:
            raise ValueError(
                "inputs require exactly date, working_directories, rulings"
            )
        if not isinstance(inputs["rulings"], dict) or not all(
            isinstance(k, str) and isinstance(v, str) and v.strip()
            for k, v in inputs["rulings"].items()
        ):
            raise ValueError(
                "rulings must map exact placeholder names to nonempty text"
            )
        if (
            not isinstance(inputs["working_directories"], str)
            or not inputs["working_directories"].strip()
        ):
            raise ValueError("working_directories must be Markdown grouped by machine")
        from datetime import date

        date.fromisoformat(inputs["date"])
    except (ValueError, TypeError, KeyError) as exc:
        raise LbError(f"invalid workflow inputs: {exc}", EXIT_USAGE) from exc
    body = section(doc.text)
    blocks = re.findall(r"(?ms)^```(?:md|markdown)\s*\n(.*?)^```\s*$", body)
    title = re.search(r"(?m)^(?:Title:|标题：)\s*`?(# [^\n`]+)", body)
    if not blocks or not title:
        raise LbError(
            "render requires an explicit title and fenced md template; maintain legacy template with lb-workflow",
            EXIT_REFUSED,
        )
    metadata = re.findall(r"(?ms)^```ya?ml\s*\n(.*?)^```\s*$", body)
    if len(metadata) > 1 or ("front matter" in body and not metadata):
        raise LbError("front matter requires one fenced yaml block", EXIT_REFUSED)
    header = "---\n" + metadata[0].rstrip() + "\n---\n\n" if metadata else ""
    content = header + title[1].rstrip("。") + "\n\n" + "\n".join(blocks)
    original = parse_text(content.encode(), doc.path, doc.root)
    expected = [
        (s.is_delivery, [(t.state, t.human) for t in s.tasks]) for s in original.stages
    ]
    # Replace only a dedicated placeholder or the contiguous directory list.
    # Prose/rulings after the list belong to the instance and must survive.
    content, count = re.subn(
        r"(?m)^(Working directories:|工作目录：)[ \t]*\n(?:[ \t]*\n)*(?:<WORKDIRS>[ \t]*\n|(?:[ \t]*- [^\n]*\n)+)",
        lambda match: match[1] + "\n\n" + inputs["working_directories"].rstrip() + "\n",
        content,
        count=1,
    )
    if count != 1:
        raise LbError(
            "working directories require a standalone <WORKDIRS> or contiguous list; ambiguous slots need template maintenance",
            EXIT_REFUSED,
        )
    replacements = {**inputs["rulings"], "DATE": inputs["date"]}
    content = re.sub(
        r"<([^<>\n]+)>",
        lambda match: replacements.get(match[1], match[0]),
        content,
    )
    remaining = re.findall(r"<[^<>\n]+>", content)
    if remaining:
        raise LbError(
            "unfilled placeholders: " + ", ".join(sorted(set(remaining))), EXIT_REFUSED
        )
    provenance = {
        "workflow": info["path"],
        "template_digest": doc.token,
        "inputs": inputs,
    }
    candidate = parse_text(content.encode(), doc.path, doc.root)
    actual = [
        (s.is_delivery, [(t.state, t.human) for t in s.tasks]) for s in candidate.stages
    ]
    if actual != expected:
        raise LbError(
            "slot substitution changed Stage/task/human-gate structure", EXIT_REFUSED
        )
    if not candidate.stages or any(
        t.state != " " for s in candidate.stages for t in s.tasks
    ):
        raise LbError("render must preserve unfinished template tasks", EXIT_REFUSED)
    return Result(
        {
            "content": content,
            "content_token": hashlib.sha256(content.encode()).hexdigest(),
            "provenance": provenance,
            "next": "lb-scaffold verifies slot authorization and creates adapter bindings",
        }
    )


def instantiate(root, name, inputs_file, token, output, dry_run):
    if lifecycle(template(root, name)) in {"draft", "deprecated", "retired"}:
        raise LbError("workflow is not available for new instances", EXIT_REFUSED)
    rendered = render(root, name, inputs_file, token)
    base = root_path(root)
    raw_destination = base / output
    if raw_destination.is_symlink():
        raise LbError("create-only output cannot be a symlink", EXIT_REFUSED)
    destination = raw_destination.resolve()
    if not destination.is_relative_to(base) or not destination.parent.is_dir():
        raise LbError("output requires an existing parent inside root", EXIT_REFUSED)
    content = rendered.value["content"]
    if destination.exists() or destination.is_symlink():
        raise LbError(
            "create-only output already exists; inspect partial scaffold before retry",
            EXIT_REFUSED,
        )
    candidate = parse_text(content.encode(), destination, base)
    issues = [i for i in check(candidate) if i["code"] not in ADVISORY_ISSUES]
    if issues:
        raise LbError(
            "invalid instance candidate: "
            + ", ".join(sorted({i["code"] for i in issues})),
            EXIT_REFUSED,
        )
    records.put(candidate, "workflow", rendered.value["provenance"])
    write_bytes(candidate, content.encode("utf-8"), dry_run, create=True)
    return Result(
        {
            "path": str(destination.relative_to(base)),
            "dry_run": dry_run,
            "version_token": state_token(candidate.data, encode(candidate.metadata)),
            "content": content if dry_run else None,
            "state_content": json.loads(encode(candidate.metadata))
            if dry_run
            else None,
            "state_path": str(state_path_for(destination, base).relative_to(base)),
            "bindings": "pending",
            "managed_workflow_complete": False,
            "next": rendered.value["next"],
        }
    )


def difference(root, log):
    doc = load(root, log)
    rows = records.read(doc, "workflow")
    if len(rows) != 1:
        raise LbError("one pinned workflow record is required", EXIT_REFUSED)
    item = rows[0][1]
    current = load(root, item["workflow"])
    return Result(
        {
            "pinned": item,
            "current_digest": current.token,
            "changed": item["template_digest"] != current.token,
            "instance_modified": False,
        }
    )


def replace_template(root, name, content_file, token, dry_run):
    """Replace one reviewed template; no companion writes or instance propagation."""
    import difflib

    doc = template(root, name)
    require_token(doc, token)
    content = safe_path(doc.root, content_file).read_bytes()
    candidate = parse_text(content, doc.path, doc.root, source=doc)
    # Lifecycle stays in the sidecar; replacement content cannot carry it inline.
    records.anchors(candidate, require_closed=True)
    info = inspect_document(candidate, name)
    if info["issues"]:
        raise LbError("invalid template: " + "; ".join(info["issues"]), EXIT_REFUSED)
    diff = "".join(
        difflib.unified_diff(
            doc.text.splitlines(True),
            candidate.text.splitlines(True),
            fromfile=str(doc.path.relative_to(doc.root)),
            tofile=str(doc.path.relative_to(doc.root)),
        )
    )
    write_bytes(doc, content, dry_run)
    return Result(
        {
            "path": str(doc.path.relative_to(doc.root)),
            "dry_run": dry_run,
            "version_token": doc.token
            if dry_run
            else state_token(content, encode(doc.metadata)),
            "diff": diff,
            "coverage": info["coverage"],
            "instances_modified": False,
        }
    )


def create_template(root, name, content_file, dry_run):
    """Create only the canonical template in an already prepared docs directory."""
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]*", name):
        raise LbError("workflow must be a simple directory name", EXIT_USAGE)
    base = root_path(root)
    directory = (base / "workflows" / name / "docs").resolve()
    if not directory.is_relative_to(base) or not directory.is_dir():
        raise LbError("prepare an approved workflow docs directory first", EXIT_REFUSED)
    if any(
        re.search(r"(?m)^## (?:Run-instance template|运行实例模板)", p.read_text())
        for p in directory.glob("*.md")
        if p.resolve().is_relative_to(base)
    ):
        raise LbError("workflow already has a template; use replace", EXIT_REFUSED)
    path = directory / (name + ".md")
    content = safe_path(base, content_file).read_bytes()
    doc = parse_text(content, path, base)
    info = inspect_document(doc, name)
    if info["issues"]:
        raise LbError("invalid template: " + "; ".join(info["issues"]), EXIT_REFUSED)
    if lifecycle(doc) != "unknown":
        raise LbError(
            "new templates must not carry an existing lifecycle", EXIT_REFUSED
        )
    content = records.append(
        doc,
        "workflow-status",
        {"id": "workflow", "status": "draft", "basis": "new template"},
    ).encode()
    doc = parse_text(content, path, base, source=doc)
    write_bytes(doc, content, dry_run, create=True)
    return Result(
        {
            "path": str(path.relative_to(base)),
            "dry_run": dry_run,
            "version_token": state_token(doc.data, encode(doc.metadata)),
            "content": doc.text,
            "state_content": json.loads(encode(doc.metadata)),
            "coverage": info["coverage"],
            "companions_created": not dry_run,
        }
    )


def lifecycle(doc):
    rows = records.read(doc, "workflow-status")
    if len(rows) > 1:
        raise LbError("duplicate workflow lifecycle", EXIT_REFUSED)
    if not rows:
        return "unknown"
    value = rows[0][1].get("status")
    if value not in {"draft", "available", "deprecated", "retired"}:
        raise LbError("invalid workflow lifecycle", EXIT_REFUSED)
    return value


def set_status(root, name, status, basis, token, dry_run):
    doc = template(root, name)
    require_token(doc, token)
    records.single_line(basis, "basis")
    transitions = {
        "unknown": {"draft", "available", "deprecated", "retired"},
        "draft": {"available", "retired"},
        "available": {"draft", "deprecated", "retired"},
        "deprecated": {"available", "retired"},
        "retired": {"draft"},
    }
    old = lifecycle(doc)
    if status not in transitions[old]:
        raise LbError("invalid workflow lifecycle transition", EXIT_REFUSED)
    item = {"id": "workflow", "status": status, "basis": basis, "previous": old}
    from logbook_cli.services.common import save

    return save(doc, records.put(doc, "workflow-status", item), dry_run, status=status)
