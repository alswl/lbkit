"""Proposed pure reducer seam: initial(target), observe(context, observation).

observe returns (new_context, events). No clocks, I/O or Task writes occur here.
The seam is private and recorded in the implementation plan, not a public adapter.
"""

import copy
import importlib.util
import unittest

from herdr_fixtures import target


class WaitStateTest(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(
            importlib.util.find_spec("logbook_cli.wait_state"),
            "T038 pure reducer is not implemented",
        )
        from logbook_cli import wait_state

        self.reducer = wait_state
        self.target = target()

    def trace(self, baseline, states):
        item = copy.deepcopy(self.target)
        item["baseline"]["state"] = baseline
        context = self.reducer.initial(item)
        events = []
        for index, state in enumerate(states):
            snapshot = {
                "binding": item["binding"],
                "state": state,
                "observed_at": f"2026-01-01T00:00:{index + 1:02}Z",
            }
            previous = context
            before = copy.deepcopy(context)
            context, emitted = self.reducer.observe(context, snapshot)
            self.assertEqual(previous, before, "Reducer must not mutate its input")
            events.extend(emitted)
        return context, events

    def test_idle_done_seen_flips_never_complete_work(self):
        _, events = self.trace("idle", ["idle", "done", "idle"])
        self.assertFalse(any(e["kind"] == "settled" for e in events))

    def test_one_settled_event_per_observed_cycle(self):
        _, events = self.trace("working", ["idle", "done", "working", "idle"])
        settled = [e for e in events if e["kind"] == "settled"]
        self.assertEqual(len(settled), 2)
        self.assertEqual(len({e["event_id"] for e in settled}), 2)

    def test_new_blocked_once_and_new_cycle_can_block_again(self):
        _, events = self.trace("idle", ["blocked", "blocked", "working", "blocked"])
        self.assertEqual(len([e for e in events if e["kind"] == "needs_input"]), 2)

    def test_initial_blocked_is_reported_once(self):
        _, events = self.trace("blocked", ["blocked", "blocked"])
        self.assertEqual(len([e for e in events if e["kind"] == "needs_input"]), 1)

    def test_native_question_identity_is_preserved_in_detected_event(self):
        context = self.reducer.initial(self.target)
        native = {
            "id": "native-question",
            "revision": "native-revision",
            "questions": [],
        }
        _, events = self.reducer.observe(
            context,
            {
                "binding": self.target["binding"],
                "state": "blocked",
                "observed_at": "2026-01-01T00:00:01Z",
                "question": native,
            },
        )
        self.assertEqual(events[0]["question"], native)
        self.assertIsNot(events[0]["question"], native)

    def test_unknown_is_not_exit_or_completion(self):
        _, events = self.trace("working", ["unknown", "unknown"])
        self.assertFalse(any(e["kind"] in {"settled", "exited"} for e in events))

    def test_exit_is_observation_not_task_completion(self):
        _, events = self.trace("working", ["exited"])
        self.assertEqual([e["kind"] for e in events], ["exited"])

    def test_changed_identity_cannot_complete_old_cycle(self):
        context = self.reducer.initial(self.target)
        changed = copy.deepcopy(self.target["binding"])
        changed["session_id"] = "replacement-session"
        _, events = self.reducer.observe(
            context,
            {
                "binding": changed,
                "state": "idle",
                "observed_at": "2026-01-01T00:00:01Z",
            },
        )
        self.assertEqual([e["kind"] for e in events], ["identity_changed"])

    def test_retained_context_suppresses_duplicate_after_serialization(self):
        import json

        context, events = self.trace("working", ["idle"])
        self.assertEqual([e["kind"] for e in events], ["settled"])
        context = json.loads(json.dumps(context))
        _, repeated = self.reducer.observe(
            context,
            {
                "binding": self.target["binding"],
                "state": "idle",
                "observed_at": "2026-01-01T00:00:02Z",
            },
        )
        self.assertFalse(any(e["kind"] == "settled" for e in repeated))

    def test_identity_loss_stays_retired_when_old_session_reappears(self):
        context = self.reducer.initial(self.target)
        changed = {**self.target["binding"], "session_id": "new-session"}
        context, events = self.reducer.observe(
            context, {"binding": changed, "state": "working"}
        )
        self.assertEqual(events[0]["kind"], "identity_changed")
        for state in ("working", "idle", "blocked"):
            context, events = self.reducer.observe(
                context, {"binding": self.target["binding"], "state": state}
            )
            self.assertEqual(events, [])

    def test_lost_baseline_does_not_claim_replay(self):
        item = copy.deepcopy(self.target)
        item.pop("baseline")
        context = self.reducer.initial(item)
        _, events = self.reducer.observe(
            context,
            {
                "binding": item["binding"],
                "state": "idle",
                "observed_at": "2026-01-01T00:00:01Z",
            },
        )
        self.assertTrue(
            any(
                e["kind"] == "observation_gap" and e["correlation"] != "observed"
                for e in events
            )
        )
        self.assertFalse(any(e["kind"] == "settled" for e in events))

    def test_dispatched_completion_between_samples_survives_resume(self):
        import json

        binding = self.target["binding"]
        context = self.reducer.initial(self.target)
        terminal = "example-terminal"
        first = {
            "binding": binding,
            "state": "done",
            "terminal_id": terminal,
            "state_change_seq": 10,
            "completion_seq": 10,
        }
        context, events = self.reducer.observe(context, first)
        self.assertEqual([event["kind"] for event in events], ["settled"])
        dispatch = {
            "operation_id": "next",
            "baseline": {
                "terminal_id": terminal,
                "state_change_seq": 10,
            },
        }
        context, events = self.reducer.observe(context, first, dispatch=dispatch)
        self.assertEqual(events, [])
        second = {**first, "state_change_seq": 12, "completion_seq": 12}
        context, events = self.reducer.observe(context, second, dispatch=dispatch)
        self.assertEqual([event["kind"] for event in events], ["settled"])
        context = json.loads(json.dumps(context))
        _, events = self.reducer.observe(context, second, dispatch=dispatch)
        self.assertEqual(events, [])

    def test_dispatched_completion_with_missing_or_discontinuous_evidence_reports_gap(
        self,
    ):
        binding = self.target["binding"]
        first = {
            "binding": binding,
            "state": "done",
            "terminal_id": "example-terminal",
            "state_change_seq": 10,
            "completion_seq": 10,
        }
        context, _ = self.reducer.observe(self.reducer.initial(self.target), first)
        baseline = {"terminal_id": first["terminal_id"], "state_change_seq": 10}
        for receipt, sample in (
            (None, first),
            (
                baseline,
                {
                    **first,
                    "terminal_id": "replacement",
                    "state_change_seq": 20,
                    "completion_seq": 20,
                },
            ),
            (baseline, {**first, "state_change_seq": 9, "completion_seq": 9}),
            (baseline, {**first, "state_change_seq": 12, "completion_seq": 10}),
        ):
            with self.subTest(receipt=receipt, sample=sample):
                dispatch = {"operation_id": "next", "baseline": receipt}
                changed, events = self.reducer.observe(
                    context, sample, dispatch=dispatch
                )
                self.assertEqual([e["kind"] for e in events], ["observation_gap"])
                _, events = self.reducer.observe(changed, sample, dispatch=dispatch)
                self.assertEqual(events, [])
        _, events = self.reducer.observe(
            context,
            {**first, "binding": {**binding, "session_id": "replacement"}},
            dispatch={"operation_id": "next", "baseline": baseline},
        )
        self.assertEqual([e["kind"] for e in events], ["identity_changed"])

    def test_completion_sampled_before_receipt_publication_is_not_repeated(self):
        binding = self.target["binding"]
        first = {
            "binding": binding,
            "state": "done",
            "terminal_id": "example-terminal",
            "state_change_seq": 12,
            "completion_seq": 12,
        }
        context, events = self.reducer.observe(self.reducer.initial(self.target), first)
        self.assertEqual([event["kind"] for event in events], ["settled"])
        dispatch = {
            "operation_id": "in-flight",
            "baseline": {
                "terminal_id": first["terminal_id"],
                "state_change_seq": 10,
            },
        }
        context, events = self.reducer.observe(context, first, dispatch=dispatch)
        self.assertEqual(events, [])
        self.assertEqual(context.get("dispatch_id"), "in-flight")
