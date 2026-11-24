"""Checkout launcher: use an already installed environment, never install on read."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
from importlib.metadata import version
from pathlib import Path
from typing import NamedTuple


def cli_version() -> str:
    checkout_version = Path(__file__).resolve().parents[2] / "VERSION"
    if checkout_version.is_file():
        return checkout_version.read_text().strip()
    return version("lbkit").replace(".dev0", "-dev")


class CliIdentity(NamedTuple):
    version: str | None
    implementation: str | None


def cli_identity() -> CliIdentity:
    package = Path(__file__).resolve().parent
    files = {
        path.relative_to(package).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in sorted(package.rglob("*.py"))
    }
    implementation = hashlib.sha256(
        json.dumps(files, sort_keys=True).encode()
    ).hexdigest()
    return CliIdentity(cli_version(), implementation)


def activate(entry: str) -> None:
    kit = Path(__file__).resolve().parents[2]
    environment = kit / ".venv"
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if python.exists() and Path(sys.prefix).resolve() != environment.resolve():
        os.execv(str(python), [str(python), entry, *sys.argv[1:]])
    def installed(name):
        try:
            return importlib.util.find_spec(name) is not None
        except ModuleNotFoundError:
            return False

    if not all(installed(name) for name in ("click", "yaml", "ruamel.yaml")):
        print(
            f"lb: CLI dependencies are missing; run uv sync --locked --no-dev --project {kit}",
            file=sys.stderr,
        )
        raise SystemExit(3)
