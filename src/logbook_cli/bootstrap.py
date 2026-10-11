"""Checkout launcher: use an already installed environment, never install on read."""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path


def activate(entry: str) -> None:
    kit = Path(__file__).resolve().parents[2]
    environment = kit / ".venv"
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if python.exists() and Path(sys.prefix).resolve() != environment.resolve():
        os.execv(str(python), [str(python), entry, *sys.argv[1:]])
    if importlib.util.find_spec("click") is None:
        print(
            f"lb: CLI dependencies are missing; run uv sync --locked --no-dev --project {kit}",
            file=sys.stderr,
        )
        raise SystemExit(3)
