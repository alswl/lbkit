#!/usr/bin/env python3
"""Compatibility entry for the shared run metrics service."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))
from logbook_cli.document import LbError, parse
from logbook_cli.run_metrics import calculate, events  # noqa: F401 (tests)
from logbook_cli.services.closeout import state_events


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--thinking", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--scope", default="logbook")
    args = parser.parse_args()
    try:
        root = Path(args.root).resolve(strict=True)
        relative = Path(args.thinking)
        if not root.is_dir() or relative.is_absolute():
            raise OSError("root must be a directory and Thinking path relative")
        path = (root / relative).resolve(strict=True)
        if not path.is_relative_to(root) or not path.is_file():
            raise OSError("Thinking must be a file inside root")
        doc = parse(path, root)
    except (OSError, UnicodeError, LbError) as exc:
        print(str(exc), file=sys.stderr)
        return 3
    try:
        print(json.dumps(calculate(state_events(doc), args.run_id, args.scope), ensure_ascii=False))
    except (ValueError, TypeError, KeyError, LbError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
