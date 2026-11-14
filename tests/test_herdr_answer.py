"""Missing native question protocols never fall back to blind terminal control."""

import unittest
from unittest.mock import patch

from herdr_fixtures import target

from logbook_cli.adapters import claude_questions, herdr
from logbook_cli.document import LbError


class HerdrAnswerTest(unittest.TestCase):
    def test_native_callback_mapping_never_uses_terminal_input(self):
        binding = {**target()["binding"], "agent_id": "claude"}
        native = {"question_id": "native-question", "revision": "native-revision"}
        receipt = {"outcome": "confirmed"}
        with (
            patch.object(claude_questions, "inspect", return_value=native),
            patch.object(claude_questions, "submit", return_value=None),
            patch.object(claude_questions, "confirm", return_value=receipt),
            patch.object(herdr, "invoke") as terminal,
        ):
            self.assertEqual(herdr.inspect_question(binding, {}), native)
            self.assertIsNone(herdr.submit_question(binding, {}))
            self.assertEqual(herdr.confirm_question(binding, {}), receipt)
        terminal.assert_not_called()

    def test_unmapped_protocol_refuses_every_question_operation_without_transport(self):
        with patch.object(herdr, "invoke") as transport:
            for operation in (
                herdr.inspect_question,
                herdr.submit_question,
                herdr.confirm_question,
            ):
                with self.subTest(operation=operation.__name__):
                    with self.assertRaisesRegex(LbError, "capability_unavailable"):
                        operation(target()["binding"], {})
        transport.assert_not_called()
