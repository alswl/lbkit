"""Diagnostics distinguish durable detection, handling, and native capabilities."""

from unittest.mock import patch

from test_observation_events import EventCase

from logbook_cli.adapters import herdr
from logbook_cli.document import LbError


class ObservationCapabilityTest(EventCase):
    def test_context_reports_unhandled_work_without_claiming_detection_failure(self):
        event = self.detected()
        before = self.observation_files()[0].read_bytes()
        context = self.context()
        self.assertIn("unresolved_events", context)
        self.assertEqual(context["unresolved_events"], [event])
        self.assertEqual(context["diagnostics"]["detected_events"], 1)
        self.assertEqual(context["diagnostics"]["unresolved_events"], 1)
        self.assertFalse(context["capabilities"]["automatic_answer"]["available"])
        self.assertEqual(self.observation_files()[0].read_bytes(), before)

    def test_message_reachability_does_not_supply_missing_native_identity(self):
        with patch.object(herdr, "invoke") as transport:
            with self.assertRaisesRegex(LbError, "identity_missing"):
                herdr.inspect_question(
                    {"pane_id": "w1:p1", "messaging_reachable": True}, {}
                )
        transport.assert_not_called()
