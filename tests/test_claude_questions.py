"""Native callback protocol tests; no live runtime or terminal input."""

import asyncio
import copy
import hashlib
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from observation_fixtures import target

from logbook_cli import observation
from logbook_cli.adapters import claude_questions as questions
from logbook_cli.document import LbError


class ClaudeQuestionTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="lbq-", dir="/tmp")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.binding = target()["binding"]
        self.payload = {
            "session_id": self.binding["session_id"],
            "hook_event_name": "PreToolUse",
            "tool_name": "AskUserQuestion",
            "tool_use_id": "native-question-one",
            "tool_input": {
                "questions": [
                    {
                        "question": "Which test label?",
                        "header": "Test",
                        "options": [
                            {"label": "Test A", "description": "First test label"},
                            {"label": "Test B", "description": "Second test label"},
                        ],
                    }
                ]
            },
            "transcript_path": "/private/example/must-not-be-read",
        }
        for mock in (
            patch.dict(os.environ, {"LBKIT_CLAUDE_QUESTION_DIR": str(self.root)}),
            patch.object(questions, "current_binding", return_value=self.binding),
        ):
            mock.start()
            self.addCleanup(mock.stop)
        self.worker = None
        self.result = None
        self.error = None
        self.addCleanup(self.join_publisher)

    def join_publisher(self):
        if self.worker:
            self.worker.join(timeout=2)
            self.assertFalse(self.worker.is_alive(), "bounded native hook must exit")

    def publish(self):
        def run():
            try:
                self.result = questions.pre_tool(self.payload, timeout=0.8)
            except Exception as exc:
                self.error = exc

        self.worker = threading.Thread(target=run)
        self.worker.start()
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline:
            try:
                return questions.inspect(self.binding, {})
            except LbError:
                if not self.worker.is_alive():
                    self.fail("native publisher did not become available: " + str(self.error))
                time.sleep(0.01)
        self.fail("native question endpoint did not become available")

    def accept(self):
        native = self.publish()
        request = {
            "question_id": native["question_id"],
            "revision": native["revision"],
            "operation_id": "native-operation-one",
            "answer": "Test A",
            "answer_digest": hashlib.sha256(observation.encode("Test A")).hexdigest(),
        }
        self.assertIsNone(questions.submit(self.binding, request))
        self.join_publisher()
        self.assertIsNone(self.error)
        answer = {
            "id": request["operation_id"],
            "question_id": request["question_id"],
            "answer_digest": request["answer_digest"],
        }
        return answer

    def confirmation(self):
        payload = copy.deepcopy(self.payload)
        payload["hook_event_name"] = "PostToolUse"
        updated = self.result["hookSpecificOutput"]["updatedInput"]
        payload["tool_input"] = updated
        payload["tool_response"] = updated
        return payload

    def test_actual_callback_result_confirms_only_matching_answer_without_plaintext_files(self):
        answer = self.accept()
        self.assertEqual(
            self.result["hookSpecificOutput"]["updatedInput"]["answers"],
            {"Which test label?": "Test A"},
        )
        with self.assertRaisesRegex(LbError, "delivery_unresolved"):
            questions.confirm(self.binding, answer, timeout=0.02)
        questions.post_tool(self.confirmation())
        receipt = questions.confirm(self.binding, answer, timeout=0.02)
        self.assertEqual(receipt["outcome"], "confirmed")
        self.assertEqual(receipt["question_id"], self.payload["tool_use_id"])
        saved = b"".join(path.read_bytes() for path in self.root.glob("*.json"))
        for private in (b"Test A", b"Which test label?", b"transcript_path"):
            self.assertNotIn(private, saved)

    def test_live_question_observation_uses_bounded_callback_not_report_tokens(self):
        native = self.publish()
        result = asyncio.run(questions.observe_native(self.binding, time.monotonic() + 0.5))
        self.assertEqual(result["id"], native["question_id"])
        self.assertEqual(result["questions"], self.payload["tool_input"]["questions"])
        self.assertEqual(result["revision"], native["revision"])

    def test_native_observation_stops_at_caller_deadline_when_callback_stalls(self):
        import socket

        endpoint = self.root / (questions.key(self.binding) + ".sock")
        with socket.socket(socket.AF_UNIX) as server:
            server.bind(str(endpoint))
            server.listen(1)
            started = time.monotonic()
            result = asyncio.run(questions.observe_native(self.binding, started + 0.05))
        self.assertIsNone(result)
        self.assertLess(time.monotonic() - started, 0.3)

    def test_wait_engine_emits_native_input_while_herdr_ui_still_reports_working(self):
        from logbook_cli import wait_state
        from logbook_cli.services import agent_wait

        native = self.publish()
        target = {"binding": self.binding, "baseline": {"state": "working"}}
        reference = {"source": "native", "agent": "claude", "kind": "id", "value": self.binding["session_id"]}
        pane = {**self.binding, "agent": "claude", "agent_session": reference}
        agent = {"name": self.binding["agent_id"], "agent": "claude", "agent_session": reference, "agent_status": "working"}

        async def invoke(machine, *args, **kwargs):
            if args[0] == "status":
                return {"server": {"running": True, "session": self.binding["server"]}}
            if args[:2] == ("agent", "get"):
                return {"result": {"agent": agent}}
            if args[:2] == ("pane", "get"):
                return {"result": {"pane": pane}}
            self.fail("native wait must be observed before entering the UI working wait")

        contexts, pending = [wait_state.initial(target)], []
        with patch.object(agent_wait.herdr, "invoke_bounded", side_effect=invoke):
            asyncio.run(agent_wait.observe_all([target], contexts, pending, [], 0.5))
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["kind"], "needs_input")
        self.assertEqual(pending[0]["question"]["id"], native["question_id"])

    def test_duplicate_post_callback_is_readonly_and_symlink_receipt_is_refused(self):
        answer = self.accept()
        payload = self.confirmation()
        questions.post_tool(payload)
        receipt = next(self.root.glob("r-*.json"))
        before = receipt.stat().st_mtime_ns
        questions.post_tool(payload)
        self.assertEqual(receipt.stat().st_mtime_ns, before)
        external = self.root / "external"
        external.write_bytes(receipt.read_bytes())
        receipt.unlink()
        receipt.symlink_to(external)
        with self.assertRaisesRegex(LbError, "capability_unavailable"):
            questions.confirm(self.binding, answer, timeout=0.01)

    def test_changed_revision_and_answer_digest_never_release_native_tool(self):
        native = self.publish()
        request = {
            "question_id": native["question_id"],
            "revision": "different-revision",
            "operation_id": "native-operation-one",
            "answer": "Test A",
            "answer_digest": hashlib.sha256(observation.encode("Test A")).hexdigest(),
        }
        with self.assertRaisesRegex(LbError, "identity_changed"):
            questions.submit(self.binding, request)
        request.update(revision=native["revision"], answer="Test B")
        with self.assertRaisesRegex(LbError, "invalid_transition"):
            questions.submit(self.binding, request)
        self.assertEqual(list(self.root.glob("*.json")), [])
        self.join_publisher()
        self.assertEqual(self.result, {})

    def test_live_binding_replacement_refuses_before_native_submission(self):
        self.publish()
        changed = {**self.binding, "session_id": "different-native-session"}
        with patch.object(questions, "current_binding", return_value=changed):
            with self.assertRaisesRegex(LbError, "identity_changed"):
                questions.inspect(self.binding, {})
        self.assertEqual(list(self.root.glob("*.json")), [])

    def test_mismatched_native_result_does_not_create_a_confirmation(self):
        answer = self.accept()
        payload = self.confirmation()
        payload["tool_response"] = {
            **payload["tool_response"],
            "answers": {"Which test label?": "Test B"},
        }
        with self.assertRaisesRegex(LbError, "identity_changed"):
            questions.post_tool(payload)
        with self.assertRaisesRegex(LbError, "delivery_unresolved"):
            questions.confirm(self.binding, answer, timeout=0.02)

    def test_unsafe_runtime_directory_is_refused_without_native_reads(self):
        self.root.chmod(0o755)
        with patch.object(questions, "current_binding") as native:
            with self.assertRaisesRegex(LbError, "capability_unavailable"):
                questions.inspect(self.binding, {})
        native.assert_not_called()

    def test_symlink_runtime_is_refused_without_native_reads(self):
        link = self.root / "link"
        link.symlink_to(self.root, target_is_directory=True)
        with (
            patch.dict(os.environ, {"LBKIT_CLAUDE_QUESTION_DIR": str(link)}),
            patch.object(questions, "current_binding") as native,
        ):
            with self.assertRaisesRegex(LbError, "capability_unavailable"):
                questions.inspect(self.binding, {})
        native.assert_not_called()

    def test_native_hook_session_mismatch_cannot_publish(self):
        self.payload["session_id"] = "not-the-observed-session"
        with self.assertRaisesRegex(LbError, "identity_changed"):
            questions.pre_tool(self.payload, timeout=0.01)
        self.assertEqual(list(self.root.iterdir()), [])
