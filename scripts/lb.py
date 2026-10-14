"""Compatibility entry point for the Logbook CLI."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Keep the historical `python scripts/lb.py` command working from any cwd.
source_root = Path(__file__).resolve().parent.parent / "src"
if str(source_root) not in sys.path:
    sys.path.insert(0, str(source_root))

if __name__ == "__main__":
    from logbook_cli.bootstrap import activate

    activate(str(Path(__file__).resolve()))

from logbook_cli.cli import cmd_task_update, main
from logbook_cli.document import EXIT_REFUSED, LbError, check, discover, parse
from logbook_cli.storage import write_bytes

__all__ = [
    "EXIT_REFUSED",
    "LbError",
    "check",
    "cmd_task_update",
    "discover",
    "main",
    "os",
    "parse",
    "write_bytes",
]

if __name__ == "__main__":
    raise SystemExit(main())
