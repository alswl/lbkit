import unittest
from types import SimpleNamespace

from logbook_cli.run_metrics import event_rows
from logbook_cli.services.closeout import state_events


class RunEventHistoryTests(unittest.TestCase):
    def setUp(self):
        self.start = {
            "run_id": "sample-run",
            "event_id": "start",
            "type": "run_start",
            "scope": "logbook",
            "at": "2024-01-01T00:00:00Z",
            "origin": "synthetic",
        }
        self.end = {
            **self.start,
            "event_id": "end",
            "type": "run_end",
            "at": "2024-01-01T00:00:01Z",
        }

    def record(self, events):
        return SimpleNamespace(
            markdown_authority=True,
            legacy_history={"run-event": {"start": self.start}},
            legacy_metadata={"run-event": {"start": self.start.copy()}},
            run_events=events,
        )

    def test_state_events_merges_history_and_current_without_double_counting(self):
        self.assertEqual(
            state_events(self.record([self.start.copy(), self.end])),
            [self.start, self.end],
        )

    def test_persisted_event_shape_validation_does_not_depend_on_readers_clock(self):
        event = {**self.start, "at": "9999-01-01T00:00:00Z"}

        self.assertEqual(event_rows([event], allow_future=True), [event])
        with self.assertRaisesRegex(ValueError, "not in the future"):
            event_rows([event])

    def test_event_replay_accounts_for_json_types_and_ignores_key_order(self):
        original = {**self.start, "reference": "synthetic", "detail": {"flag": True}}
        reordered = dict(reversed(list(original.items())))
        self.assertEqual(event_rows([original, reordered]), [original])
        with self.assertRaisesRegex(ValueError, "conflicting replay of event identity"):
            event_rows([original, {**original, "detail": {"flag": 1}}])

    def test_state_events_refuses_conflicting_historical_identity(self):
        with self.assertRaisesRegex(ValueError, "conflicting replay of event identity"):
            state_events(self.record([{**self.start, "origin": "different"}]))


if __name__ == "__main__":
    unittest.main()
