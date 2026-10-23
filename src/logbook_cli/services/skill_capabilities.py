"""Skill definitions, local readiness and attributed usage are separate facts."""

import hashlib
import json
import re
import shutil

from logbook_cli import records, task_identity
from logbook_cli.document import EXIT_REFUSED, EXIT_USAGE, LbError, root_path, safe_path
from logbook_cli.services import dispatches
from logbook_cli.services.common import Result, save


def definition(root, name):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", name):
        raise LbError("skill NAME must be a local skill directory name", EXIT_USAGE)
    base = root_path(root)
    for directory in (".agents/skills", "skills"):
        candidate = base / directory / name / "SKILL.md"
        if candidate.exists():
            path = safe_path(base, str(candidate))
            text = path.read_text()
            header = text.split("---", 2)[1] if text.startswith("---\n") else ""
            version = re.search(r"(?m)^version:\s*(.+)$", header)
            status = re.search(
                r"(?m)^status:\s*(available|deprecated|retired)\s*$", header
            )
            return {
                "name": name,
                "path": str(path.relative_to(base)),
                "definition_digest": hashlib.sha256(path.read_bytes()).hexdigest(),
                "version": version[1] if version else None,
                "status": status[1] if status else "available",
                "content": text,
            }
    raise LbError(
        "local skill definition not found; no global skill stores scanned", EXIT_REFUSED
    )


def catalog(root):
    base = root_path(root)
    names = set()
    for directory in (base / ".agents/skills", base / "skills"):
        if directory.is_dir():
            names.update(
                p.name for p in directory.iterdir() if (p / "SKILL.md").is_file()
            )
    rows = []
    for name in sorted(names):
        try:
            item = definition(root, name)
            item.pop("content")
            rows.append(item)
        except LbError as exc:
            rows.append({"name": name, "status": "unknown", "reason": exc.message})
    return Result({"definitions": rows})


def readiness(root, name, commands):
    item = definition(root, name)
    checks = []
    for command in commands:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", command):
            raise LbError(
                "--command accepts an executable name, not shell code", EXIT_USAGE
            )
        checks.append(
            {"command": command, "installed": shutil.which(command) is not None}
        )
    return Result(
        {
            "name": name,
            "definition_digest": item["definition_digest"],
            "status": "missing-tool"
            if any(not c["installed"] for c in checks)
            else "unknown",
            "tools": checks,
            "authentication": "unknown",
            "coverage": "local executable discovery only; no authentication or business probe executed",
        }
    )


def usage(root, log, thinking):
    doc, target = dispatches.documents(root, log, thinking)
    rows = [
        r
        for _, r in records.read(target, "skill-usage")
        if r.get("log") == str(doc.path.relative_to(doc.root))
    ]
    return Result(
        {
            "usage": rows,
            "version_token": target.token,
            "coverage": "attributed saved returns; declarations are not invocations and invocations are not effective adoption",
        }
    )


def record_usage(root, log, thinking, input_file, token, dry_run):
    doc, target = dispatches.documents(root, log, thinking)
    dispatches.guard(doc, target, token, False)
    try:
        data = json.loads(safe_path(doc.root, input_file).read_text())
        keys = {"id", "task_id", "skill", "state", "outcome", "basis", "at"}
        if not isinstance(data, dict) or set(data) != keys:
            raise ValueError(
                "usage input requires one JSON object with exactly: "
                + ", ".join(sorted(keys))
                + "; arrays/wrappers are not accepted. Record each return separately "
                "with the current Thinking token, then read back skill usage."
            )
        for key in keys:
            records.single_line(data[key], key)
        records.observed(data["at"])
        if data["state"] not in {"declared", "invoked", "observed"}:
            raise ValueError("usage state must be declared, invoked or observed")
        if data["outcome"] not in {"unknown", "effective", "ineffective", "failed"}:
            raise ValueError("invalid usage outcome")
        if data["state"] != "observed" and data["outcome"] != "unknown":
            raise ValueError("only an observed return can claim an outcome")
    except (ValueError, TypeError) as exc:
        raise LbError(str(exc), EXIT_USAGE) from exc
    task_identity.lookup(doc, data["task_id"])
    prior = [
        r for _, r in records.read(target, "skill-usage") if r.get("id") == data["id"]
    ]
    if len(prior) > 1:
        raise LbError("duplicate usage ID", EXIT_REFUSED)
    if prior:
        old = prior[0]
        if any(old[k] != data[k] for k in ("task_id", "skill")) or old["log"] != str(
            doc.path.relative_to(doc.root)
        ):
            raise LbError("usage identity cannot be rebound", EXIT_REFUSED)
        order = {"declared": 0, "invoked": 1, "observed": 2}
        if order[data["state"]] < order[old["state"]]:
            raise LbError("usage cannot regress to a declaration", EXIT_REFUSED)
        digest = old["definition_digest"]
    else:
        digest = definition(root, data["skill"])["definition_digest"]
    value = {
        **data,
        "log": str(doc.path.relative_to(doc.root)),
        "definition_digest": digest,
    }
    return save(target, records.put(target, "skill-usage", value), dry_run, usage=value)
