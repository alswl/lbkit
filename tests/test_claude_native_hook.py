"""Only native question callbacks may reach the opt-in answer provider."""

import os
import unittest
from unittest.mock import patch

from logbook_cli import claude_native_hook as hook
from logbook_cli.adapters import claude_questions as questions


class ClaudeHookTest(unittest.TestCase):
    def test_opt_in_question_callback_drops_transcript_and_unrelated_fields(self):
        payload = {
            "hook_event_name": "PreToolUse", "tool_name": "AskUserQuestion",
            "session_id": "native-session", "tool_use_id": "native-question",
            "tool_input": {"questions": []}, "transcript_path": "/private/example",
            "unrelated_secret": "must-not-cross-native-boundary",
        }
        with (
            patch.dict(os.environ, {questions.ENVIRONMENT: "/example/runtime"}),
            patch.object(questions, "pre_tool", return_value={"native": True}) as pre,
        ):
            self.assertEqual(hook.run(payload), {"native": True})
        self.assertNotIn("transcript_path", pre.call_args.args[0])
        self.assertNotIn("unrelated_secret", pre.call_args.args[0])
        self.assertIn("transcript_path", payload)

    def test_unconfigured_hook_cannot_invoke_native_answer_provider(self):
        with (
            patch.dict(os.environ, {questions.ENVIRONMENT: ""}),
            patch.object(questions, "pre_tool") as pre,
        ):
            self.assertEqual(hook.run({"tool_name": "AskUserQuestion"}), {})
        pre.assert_not_called()

    def test_other_tool_cannot_be_auto_approved_by_the_question_hook(self):
        with (
            patch.dict(os.environ, {questions.ENVIRONMENT: "/example/runtime"}),
            patch.object(questions, "pre_tool") as pre,
        ):
            self.assertEqual(
                hook.run({"tool_name": "Bash", "hook_event_name": "PreToolUse"}), {}
            )
        pre.assert_not_called()
