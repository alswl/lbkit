"""Isolated Observation test inputs and deterministic offline runtime controls.

No proposed production module is imported here. Barrier markers establish ordering;
bounded polling merely waits for those markers, never infers a race from elapsed time.
"""

import json
import os
import time

from coordination_helpers import CoordinationTest


def target(number=1):
    return {
        "binding": {
            "machine": "local",
            "server": "example-session",
            "workspace_id": "w1",
            "tab_id": "w1:t1",
            "pane_id": f"w1:p{number}",
            "agent_id": "codex",
            "session_id": f"example-native-{number}",
        },
        "baseline": {"state": "working", "observed_at": "2026-01-01T00:00:00Z"},
    }


def receipt(outcome="confirmed"):
    return {
        "receipt_id": "example-receipt",
        "outcome": outcome,
        "question_id": "example-question",
        "answer_digest": "example-answer-digest",
        "evidence": ["https://example.com/receipts/example"],
    }


class ObservationTest(CoordinationTest):
    def configuration(self, targets=None):
        path = self.root / "targets.json"
        path.write_text(json.dumps({"targets": [target()] if targets is None else targets}))
        return path

    def evidence(self, name="receipt.json", value=None):
        path = self.root / name
        path.write_text(json.dumps(receipt() if value is None else value))
        return path

    def barrier(self, name):
        path = self.fake / name
        os.mkfifo(path, 0o600)
        fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)
        self.addCleanup(os.close, fd)
        return fd

    def wait_checkpoint(self, name, timeout=3):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            # An append may be in flight; only inspect complete JSONL records.
            path = self.fake / "calls.jsonl"
            data = path.read_bytes() if path.exists() else b""
            rows = [json.loads(line) for line in data.split(b"\n")[:-1]]
            if any(row.get("kind") == "checkpoint" and row.get("name") == name for row in rows):
                return
            time.sleep(0.005)
        self.fail(f"offline fixture never reached checkpoint {name}")

    def submission_count(self):
        return sum(row["kind"] == "submission" for row in self.calls())
