"""Typed Event actions must preserve observation evidence and delivery guards."""

import json

from observation_fixtures import target
from test_observation_wait import ManagedWaitCase


class EventCase(ManagedWaitCase):
    def detected(self, state="blocked", targets=None):
        targets = [target()] if targets is None else targets
        self.setup_observation(targets)
        self.runtime(targets, [state] * len(targets))
        result = self.managed_wait(timeout="2")
        return result["new_events"][0]

    def event_action(
        self,
        action,
        event,
        payload,
        *,
        action_id="example-action",
        token=None,
        code=0,
        dry_run=False,
    ):
        (self.root / "action.json").write_text(json.dumps(payload))
        return self.cli(
            "agent",
            "event",
            action,
            "log.md",
            event["id"],
            "--action-id",
            action_id,
            "--input-file",
            "action.json",
            "--expect-version",
            token or self.context()["version_token"],
            *(("--dry-run",) if dry_run else ()),
            code=code,
        )


class EventTransitionTest(EventCase):
    def test_defer_preserves_question_evidence_and_business_task(self):
        event = self.detected()
        log = self.log.read_bytes()
        document = (self.root / "lb" / "log.md.json").read_bytes()
        payload = {
            "reason": "Need an owner decision",
            "responsible_party": "operator",
            "evidence": ["https://example.com/decisions/one"],
        }
        result = self.event_action("defer", event, payload)
        self.assertEqual(result["event"]["handling"], "deferred")
        saved = self.context()["observation"]["events"][0]
        self.assertEqual(saved["observation"], event["observation"])
        self.assertEqual(saved["conclusion"]["source"], "caller")
        self.assertEqual(saved["conclusion"]["payload"], payload)
        self.assertEqual(len(saved["history"]), 1)
        self.assertEqual(self.log.read_bytes(), log)
        self.assertEqual((self.root / "lb" / "log.md.json").read_bytes(), document)
        again = self.managed_wait(timeout="0.2")
        self.assertEqual(again["new_events"], [])
        self.assertEqual(again["unresolved_events"][0]["handling"], "deferred")

    def test_identical_replay_is_read_only_even_after_a_newer_action(self):
        event = self.detected()
        payload = {"reason": "Need decision", "responsible_party": "operator"}
        first = self.event_action("defer", event, payload)
        self.event_action(
            "defer",
            event,
            {**payload, "reason": "Waiting for evidence"},
            action_id="second",
        )
        before = self.observation_files()[0].read_bytes()
        replay = self.event_action("defer", event, payload)
        self.assertEqual(first["event"], replay["event"])
        self.assertEqual(self.observation_files()[0].read_bytes(), before)

    def test_action_id_content_conflict_and_stale_replay_refuse_without_writes(self):
        event = self.detected()
        old = self.context()["version_token"]
        payload = {"reason": "Need decision", "responsible_party": "operator"}
        self.event_action("defer", event, payload)
        before = self.observation_files()[0].read_bytes()
        result = self.event_action(
            "defer", event, {**payload, "reason": "Different"}, code=4
        )
        self.assertIn("invalid_transition", result.stderr)
        result = self.event_action("defer", event, payload, token=old, code=4)
        self.assertIn("version_conflict", result.stderr)
        self.assertEqual(self.observation_files()[0].read_bytes(), before)

    def test_assessment_resolves_non_question_and_blocks_new_actions(self):
        event = self.detected("idle")
        result = self.event_action("resolve", event, {"assessment": "Output reviewed"})
        self.assertEqual(result["event"]["handling"], "resolved")
        before = self.observation_files()[0].read_bytes()
        replay = self.event_action("resolve", event, {"assessment": "Output reviewed"})
        self.assertEqual(result["event"], replay["event"])
        result = self.event_action(
            "defer",
            event,
            {"reason": "Reopen", "responsible_party": "operator"},
            action_id="new",
            code=4,
        )
        self.assertIn("invalid_transition", result.stderr)
        self.assertEqual(self.observation_files()[0].read_bytes(), before)

    def test_question_cannot_be_answered_by_plain_resolve(self):
        event = self.detected()
        before = self.observation_files()[0].read_bytes()
        result = self.event_action(
            "resolve", event, {"assessment": "Answer was sent"}, code=4
        )
        self.assertIn("invalid_transition", result.stderr)
        self.assertEqual(self.observation_files()[0].read_bytes(), before)
        result = self.event_action(
            "resolve",
            event,
            {
                "obsolete": "Question withdrawn",
                "evidence": ["https://example.com/withdrawn"],
            },
        )
        self.assertEqual(result["event"]["handling"], "resolved")

    def test_dry_run_and_caller_provenance_cannot_mutate_state(self):
        event = self.detected()
        payload = {"reason": "Need decision", "responsible_party": "operator"}
        before = self.observation_files()[0].read_bytes()
        self.event_action("defer", event, payload, dry_run=True)
        self.assertEqual(self.observation_files()[0].read_bytes(), before)
        self.event_action("defer", event, {**payload, "source": "adapter"}, code=2)
        self.assertEqual(self.observation_files()[0].read_bytes(), before)

    def test_replay_does_not_rewrite_equivalent_state_serialization(self):
        event = self.detected()
        payload = {"reason": "Need decision", "responsible_party": "operator"}
        first = self.event_action("defer", event, payload)
        path = self.observation_files()[0]
        path.write_text(json.dumps(json.loads(path.read_bytes()), indent=4))
        before = path.read_bytes()
        replay = self.event_action("defer", event, payload)
        self.assertEqual(replay["event"], first["event"])
        self.assertEqual(path.read_bytes(), before)

    def test_resolve_dry_run_creates_no_action_lock_or_other_files(self):
        event = self.detected("idle")
        payload = {"assessment": "Output reviewed"}
        (self.root / "action.json").write_text(json.dumps(payload))
        before = self.snapshot()
        self.event_action("resolve", event, payload, dry_run=True)
        self.assertEqual(self.snapshot(), before)

    def test_pending_answer_blocks_obsolete_shortcut_without_losing_evidence(self):
        event = self.detected()
        path = self.observation_files()[0]
        value = json.loads(path.read_bytes())
        value["answers"] = [
            {
                "id": "example-answer",
                "event_id": event["id"],
                "status": "unknown",
                "history": [],
            }
        ]
        path.write_text(json.dumps(value))
        before = path.read_bytes()
        result = self.event_action(
            "resolve",
            event,
            {
                "obsolete": "Question withdrawn",
                "evidence": ["https://example.com/withdrawn"],
            },
            code=4,
        )
        self.assertIn("delivery_unresolved", result.stderr)
        self.assertEqual(path.read_bytes(), before)
