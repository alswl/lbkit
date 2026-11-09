#!/usr/bin/env python3
"""Offline Herdr transcript fixture. Never delegates to a real executable.

HERDR_FAKE_DIR contains script.json, counters.json and calls.jsonl. Rules match
an exact argv prefix and optionally a pane anywhere in argv. Each rule advances
through responses, repeating the last. The lock serializes concurrent children.
"""

import fcntl
import json
import os
import select
import signal
import sys
import time
from pathlib import Path


def main():
    root = Path(os.environ["HERDR_FAKE_DIR"])
    args = sys.argv[1:]
    pid = os.getpid()

    def record(kind, **data):
        # One append syscall avoids re-entrant flock deadlocks in signal handling.
        payload = (json.dumps(dict(kind=kind, pid=pid, argv=args, at=time.monotonic(), **data)) + "\n").encode()
        fd = os.open(root / "calls.jsonl", os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            os.write(fd, payload)
        finally:
            os.close(fd)

    record("start")
    with (root / "lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        rules = json.loads((root / "script.json").read_text())["rules"]
        path = root / "counters.json"
        counters = json.loads(path.read_text()) if path.exists() else {}
        response = None
        for i, rule in enumerate(rules):
            prefix = rule["argv"]
            if args[: len(prefix)] == prefix and (
                "target" not in rule or rule["target"] in args
            ):
                index = counters.get(str(i), 0)
                response = rule["responses"][min(index, len(rule["responses"]) - 1)]
                counters[str(i)] = index + 1
                break
        temporary = root / f"counters-{pid}.tmp"
        temporary.write_text(json.dumps(counters))
        os.replace(temporary, path)
    if response is None:
        record("exit", code=97)
        print("Unscripted fake Herdr invocation", file=sys.stderr)
        return 97

    def terminate(signum, frame):
        record("signal", signal=signum)
        if not response.get("ignore_term"):
            raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, terminate)
    if response.get("record_ready"):
        record("ready")

    def checkpoint(name):
        barrier = response.get("barriers", {}).get(name)
        if barrier is None:
            return
        # The controller owns a FIFO endpoint before spawning this child.
        fd = os.open(root / barrier, os.O_RDONLY | os.O_NONBLOCK)
        try:
            record("checkpoint", name=name)
            if not select.select([fd], [], [], 5)[0] or os.read(fd, 1) != b"1":
                raise RuntimeError(f"fixture barrier not released: {name}")
        finally:
            os.close(fd)

    try:
        time.sleep(response.get("delay", 0))
        checkpoint("before_submit")
        if response.get("submission"):
            record("submission", submission=response["submission"])
        checkpoint("after_submit")
        checkpoint("before_receipt")
        for stream in ("stdout", "stderr"):
            out = getattr(sys, stream)
            if stream + "_bytes" in response:
                # Stream chunks; do not allocate the requested size all at once.
                remaining = response[stream + "_bytes"]
                while remaining:
                    size = min(4096, remaining)
                    out.write("x" * size)
                    out.flush()
                    remaining -= size
            elif stream in response:
                value = response[stream]
                out.write(value if isinstance(value, str) else json.dumps(value))
                out.flush()
        checkpoint("after_receipt")
        return response.get("code", 0)
    finally:
        record("exit", code=response.get("code", 0))


if __name__ == "__main__":
    sys.exit(main())
