"""Answer ordering/replay against a controlled adapter; no real send implied."""

import json
from unittest.mock import patch

from click.testing import CliRunner
from test_observation_events import EventCase

from logbook_cli.adapters import herdr
from logbook_cli.cli import main


class AnswerCase(EventCase):
    def answer(
        self,
        action,
        event,
        payload=None,
        operation="example-operation",
        code=0,
        token=None,
        dry=False,
    ):
        if payload is not None:
            (self.root / "answer.json").write_text(json.dumps(payload))
        with CliRunner().isolation() as streams:
            argv = (
                [
                    "--root",
                    str(self.root),
                    "agent",
                    "answer",
                    action,
                    "log.md",
                    event["id"],
                    "--operation-id",
                    operation,
                ]
                if action != "reconcile"
                else [
                    "--root",
                    str(self.root),
                    "agent",
                    "answer",
                    action,
                    "log.md",
                    operation,
                ]
            )
            argv += [
                "--expect-version",
                token or self.context()["version_token"],
                "--json",
            ]
            if payload is not None:
                argv += ["--input-file", "answer.json"]
            if dry:
                argv += ["--dry-run"]
            result = main(argv)
            import sys

            sys.stdout.flush()
            sys.stderr.flush()
            output = streams[0].getvalue()
            errors = streams[1].getvalue()
        self.assertEqual(result, code, output + errors)
        return json.loads(output) if code == 0 else errors.decode()

    def request(self):
        return {
            "question_id": "question-one",
            "revision": "revision-one",
            "answer": "approved",
        }

    def confirmation(self, status="confirmed"):
        return {
            "receipt_id": "receipt-" + status,
            "outcome": status,
            "question_id": "question-one",
            "answer_digest": __import__("hashlib").sha256(b'"approved"\n').hexdigest(),
            "evidence": ["https://example.com/receipt"],
        }


class AnswerTest(AnswerCase):
    def test_current_question_cannot_be_answered_using_a_different_saved_event(self):
        event = self.detected()
        path = self.observation_files()[0]
        value = json.loads(path.read_bytes())
        value["events"][0]["observation"]["question"] = {
            "id": "different-saved-question", "revision": "different-saved-revision"
        }
        path.write_text(json.dumps(value))
        with (
            patch.object(herdr, "inspect_question") as inspect,
            patch.object(herdr, "submit_question") as send,
        ):
            error = self.answer("submit", event, self.request(), code=4)
        self.assertIn("identity_changed", error)
        inspect.assert_not_called()
        send.assert_not_called()
        self.assertEqual(self.context()["observation"]["answers"], [])

    def test_native_queue_acceptance_is_not_a_submission_receipt(self):
        event = self.detected()
        with (
            patch.object(
                herdr,
                "inspect_question",
                return_value={
                    "live_verified": True,
                    "confirmation_supported": True,
                    "question_id": "question-one",
                    "revision": "revision-one",
                },
            ),
            patch.object(herdr, "submit_question", return_value=None) as send,
            patch.object(herdr, "confirm_question", return_value=self.confirmation()),
        ):
            result = self.answer("submit", event, self.request())
        self.assertEqual(result["answer"]["status"], "confirmed")
        self.assertEqual(len(result["answer"]["history"]), 1)
        self.assertEqual(send.call_args.args[1]["operation_id"], "example-operation")
        self.assertEqual(
            send.call_args.args[1]["answer_digest"], self.confirmation()["answer_digest"]
        )

    def test_unknown_intent_exists_before_send_and_confirmation_resolves_atomically(
        self,
    ):
        event = self.detected()
        calls = []

        def send(binding, request):
            saved = self.context()["observation"]
            self.assertEqual(saved["answers"][0]["status"], "unknown")
            self.assertEqual(saved["events"][0]["handling"], "pending")
            self.assertNotIn("approved", self.observation_files()[0].read_text())
            calls.append(request)
            return self.confirmation("submitted")

        with (
            patch.object(
                herdr,
                "inspect_question",
                return_value={
                    "live_verified": True,
                    "question_id": "question-one",
                    "revision": "revision-one",
                    "confirmation_supported": True,
                },
            ),
            patch.object(herdr, "submit_question", side_effect=send),
            patch.object(herdr, "confirm_question", return_value=self.confirmation()),
        ):
            result = self.answer("submit", event, self.request())
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["answer"]["status"], "confirmed")
        saved = self.context()["observation"]
        self.assertEqual(saved["events"][0]["handling"], "resolved")
        self.assertEqual(saved["events"][0]["conclusion"]["source"], "adapter")
        self.assertEqual(saved["answers"][0]["status"], "confirmed")

    def test_confirmed_replay_does_not_read_live_question_or_send_again(self):
        event = self.detected()
        with (
            patch.object(
                herdr,
                "inspect_question",
                return_value={
                    "live_verified": True,
                    "question_id": "question-one",
                    "revision": "revision-one",
                    "confirmation_supported": True,
                },
            ),
            patch.object(
                herdr, "submit_question", return_value=self.confirmation("submitted")
            ),
            patch.object(herdr, "confirm_question", return_value=self.confirmation()),
        ):
            first = self.answer("submit", event, self.request())
        with (
            patch.object(
                herdr,
                "inspect_question",
                side_effect=AssertionError("no live read on replay"),
            ),
            patch.object(
                herdr, "submit_question", side_effect=AssertionError("duplicate send")
            ),
        ):
            replay = self.answer("submit", event, self.request())
            self.assertEqual(first["answer"], replay["answer"])
            self.answer(
                "submit", event, {**self.request(), "answer": "changed"}, code=4
            )

    def test_lost_send_receipt_blocks_same_and_new_id_retries(self):
        event = self.detected()
        with (
            patch.object(
                herdr,
                "inspect_question",
                return_value={
                    "live_verified": True,
                    "question_id": "question-one",
                    "revision": "revision-one",
                    "confirmation_supported": True,
                },
            ),
            patch.object(
                herdr, "submit_question", side_effect=OSError("lost receipt")
            ) as send,
        ):
            result = self.answer("submit", event, self.request())
            self.assertEqual(result["answer"]["status"], "unknown")
            self.answer("submit", event, self.request())
            self.answer("submit", event, self.request(), operation="another", code=4)
            self.assertEqual(send.call_count, 1)

    def test_unsupported_capability_saves_no_intent_and_sends_nothing(self):
        event = self.detected()
        before = self.observation_files()[0].read_bytes()
        with patch.object(herdr, "submit_question") as send:
            error = self.answer("submit", event, self.request(), code=4)
        self.assertIn("capability_unavailable", error)
        send.assert_not_called()
        self.assertEqual(self.observation_files()[0].read_bytes(), before)

    def test_external_prepare_never_sends_and_cannot_convert_mode(self):
        event = self.detected()
        intent = {
            "answer_digest": self.confirmation()["answer_digest"],
            "question_id": "question-one",
            "execution_owner": "example-executor",
            "evidence": ["https://example.com/intent"],
        }
        with patch.object(
            herdr, "submit_question", side_effect=AssertionError("no send")
        ):
            prepared = self.answer("prepare", event, intent)
            self.assertEqual(prepared["answer"]["status"], "unknown")
            self.answer("submit", event, self.request(), code=4)
            self.answer("prepare", event, intent, operation="new-id", code=4)
            self.assertEqual(
                self.context()["observation"]["events"][0]["handling"], "pending"
            )

    def test_caller_confirmation_and_receipt_replay_are_atomic_and_attributed(self):
        event = self.detected()
        intent = {
            "answer_digest": self.confirmation()["answer_digest"],
            "question_id": "question-one",
            "execution_owner": "example-executor",
            "evidence": ["https://example.com/intent"],
        }
        self.answer("prepare", event, intent)
        with patch.object(
            herdr,
            "submit_question",
            side_effect=AssertionError("reconcile must not send"),
        ):
            first = self.answer("reconcile", event, self.confirmation())
            saved = self.context()["observation"]
            self.assertEqual(saved["events"][0]["handling"], "resolved")
            self.assertEqual(saved["events"][0]["conclusion"]["source"], "caller")
            before = self.observation_files()[0].read_bytes()
            replay = self.answer("reconcile", event, self.confirmation())
            self.assertEqual(first["answer"], replay["answer"])
            self.assertEqual(self.observation_files()[0].read_bytes(), before)
            self.answer(
                "reconcile",
                event,
                {**self.confirmation(), "outcome": "not_submitted"},
                code=4,
            )
            self.answer(
                "reconcile", event, {**self.confirmation(), "source": "adapter"}, code=4
            )

    def test_non_submission_requires_affirmative_evidence_and_external_executor_exit(
        self,
    ):
        event = self.detected()
        intent = {
            "answer_digest": self.confirmation()["answer_digest"],
            "question_id": "question-one",
            "execution_owner": "example-executor",
            "evidence": ["https://example.com/intent"],
        }
        self.answer("prepare", event, intent)
        receipt = self.confirmation("not_submitted")
        self.answer("reconcile", event, receipt, code=4)
        self.answer(
            "reconcile",
            event,
            {
                **receipt,
                "non_submission": "Executor never sent",
                "executor_terminated": False,
            },
            code=4,
        )
        result = self.answer(
            "reconcile",
            event,
            {
                **receipt,
                "non_submission": "Executor never sent",
                "executor_terminated": True,
            },
        )
        self.assertEqual(result["answer"]["status"], "not_submitted")
        self.answer("prepare", event, intent, operation="new-attempt")

    def test_reconcile_dry_run_and_stale_token_preserve_delivery_uncertainty(self):
        event = self.detected()
        intent = {
            "answer_digest": self.confirmation()["answer_digest"],
            "question_id": "question-one",
            "execution_owner": "example-executor",
            "evidence": ["https://example.com/intent"],
        }
        old = self.context()["version_token"]
        self.answer("prepare", event, intent)
        before = self.observation_files()[0].read_bytes()
        self.answer("reconcile", event, self.confirmation(), token=old, code=4)
        self.answer("reconcile", event, self.confirmation(), dry=True)
        self.assertEqual(self.observation_files()[0].read_bytes(), before)

    def test_unverified_binding_or_changed_question_revision_never_creates_intent(self):
        event = self.detected()
        valid = {
            "live_verified": True,
            "question_id": "question-one",
            "revision": "revision-one",
            "confirmation_supported": True,
        }
        before = self.observation_files()[0].read_bytes()
        for change, category in [
            ({"live_verified": False}, "identity_missing"),
            ({"question_id": "other-question"}, "identity_changed"),
            ({"revision": "other-revision"}, "identity_changed"),
            ({"confirmation_supported": False}, "capability_unavailable"),
        ]:
            with (
                self.subTest(change=change),
                patch.object(
                    herdr, "inspect_question", return_value={**valid, **change}
                ),
                patch.object(herdr, "submit_question") as send,
            ):
                error = self.answer("submit", event, self.request(), code=4)
                self.assertIn(category, error)
                send.assert_not_called()
                self.assertEqual(self.observation_files()[0].read_bytes(), before)

    def test_confirmation_timeout_keeps_submitted_and_never_retries_send(self):
        event = self.detected()
        with (
            patch.object(
                herdr,
                "inspect_question",
                return_value={
                    "live_verified": True,
                    "question_id": "question-one",
                    "revision": "revision-one",
                    "confirmation_supported": True,
                },
            ),
            patch.object(
                herdr, "submit_question", return_value=self.confirmation("submitted")
            ) as send,
            patch.object(
                herdr,
                "confirm_question",
                side_effect=TimeoutError("bounded confirmation expired"),
            ),
        ):
            first = self.answer("submit", event, self.request())
            self.assertEqual(first["answer"]["status"], "submitted")
            self.answer("submit", event, self.request())
            self.answer(
                "submit", event, self.request(), operation="different-id", code=4
            )
            self.assertEqual(send.call_count, 1)
            self.assertEqual(
                self.context()["observation"]["events"][0]["handling"], "pending"
            )
