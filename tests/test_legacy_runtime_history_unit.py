"""Unit coverage for historical Attempt reconciliation and runtime guards."""

from copy import deepcopy
from unittest import TestCase

from logbook_cli import legacy_conversion
from logbook_cli.document import LbError
from logbook_cli.services import readiness, transport


class LegacyRuntimeHistoryTest(TestCase):
    def closed_dispatch(self):
        edges = (
            ("prepared", "sent", 1),
            ("sent", "acknowledged", 2),
            ("acknowledged", "returned", 5),
            ("returned", "closed", 6),
        )
        return {
            "status": "closed",
            "history": [
                {
                    "from": a,
                    "to": b,
                    "basis": "example evidence",
                    "at": f"2025-01-01T00:0{t}:00Z",
                }
                for a, b, t in edges
            ],
            "attempts": [
                {
                    "id": "attempt-1",
                    "status": "interrupted",
                    "started_at": "2025-01-01T00:03:00Z",
                    "ended_at": "2025-01-01T00:04:00Z",
                    "basis": "example return",
                }
            ],
        }

    def test_attempt_requires_complete_closeout_and_ordered_terminal_evidence(self):
        record = self.closed_dispatch()
        self.assertEqual(
            legacy_conversion.closed_attempts("dispatch-1", record), ["attempt-1"]
        )
        for changes, message in (
            ({"status": "returned"}, "requires a closed Dispatch"),
            ({"history": []}, "complete transition history"),
            (
                {"attempts": [record["attempts"][0] | {"status": "started"}]},
                "recorded terminal state",
            ),
            (
                {
                    "attempts": [
                        record["attempts"][0] | {"ended_at": "2025-01-01T00:06:00Z"}
                    ]
                },
                "time bounds",
            ),
            ({"attempts": record["attempts"] * 2}, "identity"),
        ):
            with (
                self.subTest(changes=changes),
                self.assertRaisesRegex(LbError, message),
            ):
                legacy_conversion.closed_attempts("dispatch-1", record | changes)

    def test_terminal_attempt_protects_same_task_even_with_contradictory_claim(self):
        operation = {
            "id": "operation-1",
            "request": {"dispatch_id": "dispatch-1"},
            "outcome": "submitted",
            "legacy_task_id": "task-first",
            "legacy_attempt_ids": ["attempt-1"],
        }
        ex = {
            "operations": {"operation-1": operation},
            "facts": [
                {
                    "kind": "business-action",
                    "outcome": "not_started",
                    "operation_id": "operation-1",
                },
            ],
        }
        self.assertTrue(readiness.unresolved_operation(ex, "task-first"))
        self.assertFalse(readiness.unresolved_operation(ex, "task-replacement"))
        with self.assertRaisesRegex(LbError, "terminal Attempt already started"):
            transport.task_send_guard(ex, "task-first", "fresh-operation", {})
        unknown = deepcopy(ex)
        unknown["operations"]["operation-1"]["outcome"] = "unknown"
        with self.assertRaisesRegex(LbError, "unknown delivery blocks"):
            transport.task_send_guard(
                unknown, "task-replacement", "fresh-operation", {}
            )
