"""Action ownership and receipt faults, positioned inside the actual send callback."""

import json
from unittest.mock import patch

from observation_fixtures import target
from test_observation_answers import AnswerCase

from logbook_cli import storage
from logbook_cli.adapters import herdr


class AnswerRaceTest(AnswerCase):
    def test_inflight_submit_excludes_reconcile_and_target_replacement(self):
        event = self.detected()
        calls = []

        def send(binding, request):
            # The callback is the barrier: intent is durable and send owns the
            # binding action lock, but no state lock is held across the call.
            current = self.context()["version_token"]
            result = self.cli(
                "agent",
                "answer",
                "reconcile",
                "log.md",
                "example-operation",
                "--expect-version",
                current,
                code=4,
            )
            self.assertIn("delivery_unresolved", result.stderr)
            self.configuration([target(2)])
            result = self.configure(self.context()["version_token"], code=4)
            self.assertIn("delivery_unresolved", result.stderr)
            calls.append(True)
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
        self.assertEqual(result["answer"]["status"], "confirmed")
        self.assertEqual(calls, [True])
        self.assertEqual(self.context()["observation"]["targets"], [target()])

    def receipt_failure(self, failure_status):
        event = self.detected()
        replace = storage.replace_bytes_at

        def fail_save(directory, name, data, expected):
            value = json.loads(data)
            if any(row["status"] == failure_status for row in value["answers"]):
                raise OSError("injected receipt persistence failure")
            return replace(directory, name, data, expected)

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
            patch.object(herdr, "confirm_question", return_value=self.confirmation()),
            patch.object(storage, "replace_bytes_at", side_effect=fail_save),
        ):
            self.answer("submit", event, self.request(), code=3)
            status = self.context()["observation"]["answers"][0]["status"]
            self.assertEqual(
                status, "unknown" if failure_status == "submitted" else "submitted"
            )
            self.answer("submit", event, self.request())
            self.answer(
                "submit", event, self.request(), operation="new-operation", code=4
            )
            self.assertEqual(send.call_count, 1)
        self.assertEqual(
            self.context()["observation"]["events"][0]["handling"], "pending"
        )

    def test_failed_receipt_save_keeps_unknown_and_never_resends(self):
        self.receipt_failure("submitted")

    def test_failed_confirmation_save_keeps_submitted_and_event_unresolved(self):
        self.receipt_failure("confirmed")

    def test_lost_parent_descriptor_never_falls_back_to_current_directory(self):
        from contextlib import nullcontext

        from logbook_cli import observation
        from logbook_cli.document import LbError
        from logbook_cli.services.common import load

        self.setup_observation()
        doc = load(str(self.root), "log.md")
        with (
            patch.object(
                observation, "parent_directory", return_value=nullcontext(None)
            ),
            patch(
                "os.open",
                side_effect=AssertionError(
                    "must not open relative to current directory"
                ),
            ),
        ):
            with self.assertRaisesRegex(LbError, "invalid_transition"):
                with observation.action_lock(doc, target()["binding"]):
                    self.fail("unsafe parent admitted")
        with patch(
            "os.open", side_effect=AssertionError("must not create cwd temporary")
        ):
            with self.assertRaisesRegex(LbError, "invalid_transition"):
                storage.replace_bytes_at(None, "unexpected.json", b"{}", None)

    def test_directory_fsync_failure_after_confirmation_is_not_success(self):
        import os
        import stat

        event = self.detected()
        path = self.observation_files()[0]
        sync = os.fsync

        def fail_confirmed_directory(fd):
            descriptor = os.fstat(fd)
            directory = path.parent.stat()
            if (
                stat.S_ISDIR(descriptor.st_mode)
                and (descriptor.st_dev, descriptor.st_ino)
                == (directory.st_dev, directory.st_ino)
                and any(
                    row["status"] == "confirmed"
                    for row in json.loads(path.read_bytes())["answers"]
                )
            ):
                raise OSError("injected post-replace directory fsync failure")
            return sync(fd)

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
            patch("os.fsync", side_effect=fail_confirmed_directory),
        ):
            error = self.answer("submit", event, self.request(), code=3)
            self.assertIn("persistence_failed", error)
        saved = self.context()["observation"]
        self.assertEqual(saved["answers"][0]["status"], "confirmed")
        self.assertEqual(saved["events"][0]["handling"], "resolved")
