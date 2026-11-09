"""Stopped-listener target changes retain cursor identity and unresolved work."""

import copy
import json

from observation_fixtures import target
from test_observation_answers import AnswerCase


class ObservationTargetTest(AnswerCase):
    def test_add_remove_readd_preserves_cursors_and_retired_events(self):
        targets = [target(1), target(2)]
        self.setup_observation(targets)
        self.runtime(targets, ["blocked", "blocked"])
        self.managed_wait()
        self.managed_wait()
        before = self.context()["observation"]
        self.configuration([target(1), target(3)])
        self.configure(self.context()["version_token"])
        changed = self.context()["observation"]
        self.assertEqual(changed["contexts"][0], before["contexts"][0])
        self.assertEqual(changed["events"], before["events"])
        self.configuration(targets)
        self.configure(self.context()["version_token"])
        restored = self.context()["observation"]
        self.assertEqual(restored["contexts"], before["contexts"])
        self.runtime(targets, ["blocked", "blocked"])
        self.assertEqual(self.managed_wait(timeout="0.3")["new_events"], [])

    def test_reordering_is_a_noop_and_changed_known_baseline_refuses(self):
        targets = [target(1), target(2)]
        self.setup_observation(targets)
        self.runtime(targets, ["blocked", "blocked"])
        self.managed_wait()
        original = self.observation_files()[0].read_bytes()
        self.configuration(list(reversed(targets)))
        self.configure(self.context()["version_token"])
        self.assertEqual(self.observation_files()[0].read_bytes(), original)
        changed = copy.deepcopy(targets)
        changed[0]["baseline"]["state"] = "idle"
        self.configuration(changed)
        result = self.configure(self.context()["version_token"], code=4)
        self.assertIn("invalid_transition", result.stderr)
        self.assertEqual(self.observation_files()[0].read_bytes(), original)

    def test_retired_terminal_identity_cannot_be_rearmed(self):
        self.setup_observation()
        path = self.observation_files()[0]
        value = json.loads(path.read_bytes())
        value["contexts"][0].update(state="exited", reported="exited", armed=False)
        path.write_text(json.dumps(value))
        self.configuration([target(2)])
        self.configure(self.context()["version_token"])
        self.configuration([target(1)])
        before = path.read_bytes()
        result = self.configure(self.context()["version_token"], code=4)
        self.assertIn("invalid_transition", result.stderr)
        self.assertEqual(path.read_bytes(), before)

    def test_prepared_unknown_answer_prevents_replacement_after_executor_lock_releases(
        self,
    ):
        event = self.detected()
        self.answer(
            "prepare",
            event,
            {
                "answer_digest": self.confirmation()["answer_digest"],
                "question_id": "question-one",
                "execution_owner": "example-executor",
                "evidence": ["https://example.com/intent"],
            },
        )
        self.configuration([target(2)])
        before = self.observation_files()[0].read_bytes()
        result = self.configure(self.context()["version_token"], code=4)
        self.assertIn("delivery_unresolved", result.stderr)
        self.assertEqual(self.observation_files()[0].read_bytes(), before)
