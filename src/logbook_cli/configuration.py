"""lbkit.yaml (settings, agents) and lbkit-skills.yaml (recipes): round-trip YAML,
reference checks and guarded writes."""

from __future__ import annotations

import copy
import difflib
import fcntl
import hashlib
import io
import json
import re
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError
from ruamel.yaml.tokens import AliasToken, TagToken

from logbook_cli.document import EXIT_REFUSED, LbError, safe_path

NAME = "lbkit.yaml"
SKILLS_NAME = "lbkit-skills.yaml"
GROUPS = {"agents": NAME, "recipes": SKILLS_NAME}
VERSION = "0.2.0"
ID = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
TRANSITIONS = {
    "draft": {"available", "retired"},
    "available": {"deprecated"},
    "deprecated": {"available", "retired"},
    "retired": {"draft"},
}


def refuse(message):
    raise LbError(message, EXIT_REFUSED)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def yaml_engine():
    engine = YAML()
    engine.preserve_quotes = True
    engine.allow_duplicate_keys = False
    engine.width = 4096
    return engine


def decode(data: bytes):
    try:
        text = data.decode("utf-8")
        if any(
            isinstance(token, (AliasToken, TagToken))
            for token in yaml_engine().scan(text)
        ):
            refuse(
                "YAML aliases and explicit tags are unsupported; expand them explicitly before editing"
            )
        value = yaml_engine().load(text)
    except (YAMLError, UnicodeError) as exc:
        refuse(f"invalid YAML: {exc}")
    if not isinstance(value, dict):
        refuse("input must be a YAML mapping")

    def check_keys(item):
        if isinstance(item, dict):
            if any(not isinstance(key, str) for key in item):
                refuse("configuration mapping keys must be strings")
            for child in item.values():
                check_keys(child)
        elif isinstance(item, list):
            for child in item:
                check_keys(child)

    check_keys(value)
    return value


def encode(value) -> bytes:
    output = io.StringIO()
    yaml_engine().dump(value, output)
    return output.getvalue().encode("utf-8")


def strings(value, where):
    if not isinstance(value, list) or any(
        not isinstance(v, str) or not v.strip() for v in value
    ):
        refuse(f"{where} must be an array of non-empty strings")


def common(group, identity, obj):
    if not isinstance(identity, str) or not ID.fullmatch(identity):
        refuse(f"{group} ID must use kebab-case: {identity}")
    if (
        not isinstance(obj, dict)
        or not isinstance(obj.get("status"), str)
        or obj["status"] not in TRANSITIONS
    ):
        refuse(f"{group}.{identity} requires a valid status")
    for key in ("name", "description"):
        if key in obj and not isinstance(obj[key], str):
            refuse(f"{group}.{identity}.{key} must be text")


def validate(value, name=NAME):
    if value.get("version") != VERSION:
        refuse(f"version must be {VERSION}; format release decision is pending")
    if name == SKILLS_NAME:
        if not isinstance(value.get("recipes"), dict):
            refuse("recipes must be a mapping")
        for identity, obj in value["recipes"].items():
            common("recipes", identity, obj)
            for key in ("applies_to", "excludes", "steps"):
                strings(obj.get(key), key)
            if not obj["steps"]:
                refuse("recipe steps must not be empty")
            companions = obj.get("companions")
            if not isinstance(companions, list):
                refuse("companions must be an array")
            for item in companions:
                if not isinstance(item, dict) or any(
                    not isinstance(item.get(k), str) or not item[k].strip()
                    for k in ("skill", "when")
                ):
                    refuse("companions require skill and when")
        return value
    for key in ("settings", "agents"):
        if not isinstance(value.get(key), dict):
            refuse(f"{key} must be a mapping")
    settings = value["settings"]
    for key in ("documents", "runtime", "roles", "browser", "auth", "limits"):
        if key in settings and not isinstance(settings[key], dict):
            refuse(f"settings.{key} must be a mapping")
    for identity, obj in value["agents"].items():
        common("agents", identity, obj)
        launcher = obj.get("launcher")
        if (
            not isinstance(launcher, dict)
            or not isinstance(launcher.get("command"), str)
            or not launcher["command"].strip()
        ):
            refuse(f"agents.{identity}.launcher requires command")
        strings(launcher.get("args"), "launcher.args")
        if not isinstance(obj.get("model"), str) or not obj["model"].strip():
            refuse(f"agents.{identity} requires model")
        if obj.get("deployment") not in ("internal", "external", "unknown"):
            refuse("deployment must be internal, external or unknown")
        strings(obj.get("suitable_for"), "suitable_for")
    default = settings.get("default_agent")
    if default is not None:
        if not isinstance(default, str) or default not in value["agents"]:
            refuse(f"default_agent references missing agent {default}")
        if value["agents"][default]["status"] != "available":
            refuse("default_agent must reference an available agent")
    return value


def read(root: Path, name=NAME):
    """Return path, bytes and value; a missing skills file reads as empty with no bytes."""
    if (root / name).is_symlink():
        refuse(f"{name} must not be a symlink")
    if name == SKILLS_NAME and not (root / name).exists():
        return root.resolve() / name, None, {"version": VERSION, "recipes": {}}
    path = safe_path(root.resolve(), name)
    if path.is_symlink() or not path.is_file():
        refuse(
            f"{name} must be an existing regular file; copy .lbkit/{name.removesuffix('.yaml')}.template.yaml first"
        )
    data = path.read_bytes()
    value = validate(decode(data), name)
    return path, data, value


def token_of(data):
    return digest(data) if data is not None else None


def snapshot(root):
    path, data, value = read(root)
    skills_path, skills_data, skills = read(root, SKILLS_NAME)
    return {
        "path": str(path),
        "version_token": digest(data),
        "config": value,
        "skills": {
            "path": str(skills_path),
            "exists": skills_data is not None,
            "version_token": token_of(skills_data),
            "config": skills,
        },
    }


def object_digest(obj):
    return digest(
        json.dumps(
            obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str
        ).encode()
    )


def resolve(root, agent=None, overrides=None):
    _, data, value = read(root)
    effective = copy.deepcopy(value["settings"])
    sources = {}

    def leaves(obj, prefix, source):
        for key, val in obj.items():
            dotted = f"{prefix}.{key}" if prefix else key
            if isinstance(val, dict):
                leaves(val, dotted, source)
            else:
                sources[dotted] = source

    leaves(effective, "", NAME + ":settings")

    def merge(target, patch, prefix=""):
        for key, val in patch.items():
            dotted = f"{prefix}.{key}" if prefix else key
            if isinstance(val, dict) and isinstance(target.get(key), dict):
                merge(target[key], val, dotted)
            else:
                target[key] = copy.deepcopy(val)
                for old in list(sources):
                    if old == dotted or old.startswith(dotted + "."):
                        del sources[old]
                if isinstance(val, dict):
                    leaves(val, dotted, "input_file:settings")
                else:
                    sources[dotted] = "input_file:settings"

    if overrides:
        if set(overrides) != {"settings"} or not isinstance(
            overrides["settings"], dict
        ):
            refuse("resolve input must contain only settings")
        merge(effective, overrides["settings"])
    if agent is not None:
        effective["default_agent"] = agent
        sources["default_agent"] = "--agent"
    candidate = copy.deepcopy(value)
    candidate["settings"] = effective
    validate(candidate)
    selected = effective.get("default_agent")
    obj = value["agents"].get(selected) if selected else None
    return {
        "version_token": digest(data),
        "settings": effective,
        "sources": sources,
        "agent_id": selected,
        "agent_source": f"{NAME}:agents.{selected}" if selected else None,
        "agent": obj,
        "agent_digest": object_digest(obj) if obj else None,
        "readiness": "not_checked",
        "execution": "none",
    }


def write_existing(path, before, after, token, dry_run):
    if token != digest(before):
        refuse("version conflict; reread config show and use its version_token")
    result = {
        "path": str(path),
        "version_token": digest(after),
        "dry_run": dry_run,
        "diff": "".join(
            difflib.unified_diff(
                before.decode().splitlines(True),
                after.decode().splitlines(True),
                fromfile=path.name,
                tofile=path.name,
            )
        ),
    }
    if dry_run or after == before:
        return result
    # The stable parent directory lock serializes CLI writers across atomic replacements.
    with directory_lock(path.parent):
        if path.is_symlink() or path.read_bytes() != before:
            refuse("version conflict during write; reread config show")
        import os
        import tempfile

        fd, temporary = tempfile.mkstemp(prefix=".lb-config-", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(after)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, path.stat().st_mode)
            if path.read_bytes() != before:
                refuse("configuration changed during write")
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    return result


class directory_lock:
    def __init__(self, path):
        import os

        self.fd = os.open(path, os.O_RDONLY)

    def __enter__(self):
        fcntl.flock(self.fd, fcntl.LOCK_EX)

    def __exit__(self, *args):
        import os

        fcntl.flock(self.fd, fcntl.LOCK_UN)
        os.close(self.fd)


def mutate(root, group, operation, identity, payload, token, dry_run):
    name = GROUPS[group]
    path, before, value = read(root, name)
    if before is None:
        refuse(f"{name} does not exist; copy .lbkit/lbkit-skills.template.yaml first")
    if token != digest(before):
        refuse("version conflict; reread config show")
    entries = value[group]
    if operation == "create":
        if identity in entries:
            refuse(f"{identity} already exists")
        if payload.get("status", "draft") != "draft":
            refuse("new objects must start as draft")
        entries[identity] = {"status": "draft", **payload}
    else:
        if identity not in entries:
            refuse(f"unknown {group} ID: {identity}")
        if operation == "remove":
            if entries[identity]["status"] != "retired":
                refuse("retire an object before removing it")
            if group == "agents" and value["settings"].get("default_agent") == identity:
                refuse("agent is still the default_agent; no cascade is performed")
            del entries[identity]
        elif operation == "set-status":
            if set(payload) != {"status"}:
                refuse("set-status input must contain only status")
            old, new = entries[identity]["status"], payload["status"]
            if not isinstance(new, str) or new not in TRANSITIONS[old]:
                refuse(f"illegal status transition: {old} -> {new}")
            entries[identity]["status"] = new
        else:
            if "status" in payload:
                refuse("use set-status to change lifecycle")

            def merge(target, patch):
                for key, val in patch.items():
                    if isinstance(val, dict) and isinstance(target.get(key), dict):
                        merge(target[key], val)
                    else:
                        target[key] = val

            merge(entries[identity], payload)
    validate(value, name)
    return write_existing(path, before, encode(value), token, dry_run)
