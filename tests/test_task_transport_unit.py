import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import Mock, patch

from logbook_cli.document import LbError, parse_text
from logbook_cli.services.transport import send_task, task_send_guard


class TaskTransportTests(unittest.TestCase):
    def test_unknown_any_task_prevents_redelegation(self):
        with self.assertRaises(LbError):
            task_send_guard(
                {
                    "operations": {
                        "old": {
                            "outcome": "unknown",
                            "request": {"task_id": "old-task"},
                        }
                    }
                },
                "new-task",
                "new-op",
                {},
            )

    def test_id_conflict_and_submitted_replay(self):
        request = {"task_id": "a", "binding_id": "b"}
        ex = {"operations": {"op": {"outcome": "submitted", "request": request}}}
        self.assertIsNotNone(task_send_guard(ex, "a", "op", request))
        with self.assertRaises(LbError):
            task_send_guard(ex, "a", "op", {"task_id": "other"})

    def test_submitted_delivery_requires_business_action_evidence(self):
        ex = {
            "operations": {
                "old": {
                    "outcome": "submitted",
                    "request": {"task_id": "a", "binding_id": "old"},
                    "receipt": {"transport": "submitted"},
                }
            }
        }
        request = {"task_id": "a", "binding_id": "new"}
        with self.assertRaisesRegex(LbError, "no business-action outcome"):
            task_send_guard(ex, "a", "new-op", request)
        ex["facts"] = [
            {"kind": "business-action", "operation_id": "old", "outcome": "started"}
        ]
        self.assertIsNone(task_send_guard(ex, "a", "new-op", request))
        with self.assertRaisesRegex(LbError, "original operation ID"):
            task_send_guard(ex, "a", "new-op", ex["operations"]["old"]["request"])

    def test_first_send_without_confirmation_or_preflight_stops_before_host(self):
        self.assert_first_send_stops_before_host("")

    def test_first_send_with_route_level_dialogue_blocker_stops_before_host(self):
        self.assert_first_send_stops_before_host(
            "- [ ] 🔮 Confirm the scope of a later task\n"
        )

    def test_changes_between_live_check_and_intent_prevent_send(self):
        self.assert_first_send_stops_before_host("", change_before_intent="document")

    def test_concurrent_intent_occupies_execution_version(self):
        self.assert_first_send_stops_before_host("", change_before_intent="execution")

    def assert_first_send_stops_before_host(
        self, later_task, change_before_intent=None
    ):
        root = Path("/example")
        markdown = "# Work\n\n## Stage 1\n\n- [ ] Prepare fixture\n" + later_task
        doc = parse_text(markdown.encode(), root / "log.md", root)
        task = doc.stages[0].tasks[0]
        binding = {
            "subject": {"kind": "agent", "subject_id": "worker"},
            "session_id": "session",
        }
        envelope = {
            "identity": {"run_id": "run"},
            "execution": {
                "operations": {},
                "tasks": {
                    "task": {
                        "current_binding_id": "binding",
                        "execution_bindings": {"binding": binding},
                    }
                },
            },
        }
        message_file = Mock()
        message_file.read_text.return_value = "Prepare fixture"
        changed = parse_text((markdown + "\nChanged route.\n").encode(), doc.path, root)
        synced = [(doc, task), (doc, task), (changed, task)]
        tokens = ["execution-token", "occupied-token"]

        def attempt_transport(*args, before_mutation):
            before_mutation()
            self.fail("adapter persisted intent for a changed document")

        with (
            patch(
                "logbook_cli.repository.require_synced",
                side_effect=synced if change_before_intent == "document" else None,
                return_value=(doc, task),
            ),
            patch("logbook_cli.document.safe_path", return_value=message_file),
            patch("logbook_cli.unified.writer", side_effect=lambda *a: nullcontext()),
            patch(
                "logbook_cli.unified.locate", return_value=(root / "run.json", envelope)
            ),
            patch(
                "logbook_cli.unified.section_token",
                side_effect=tokens if change_before_intent == "execution" else None,
                return_value="execution-token",
            ),
            patch(
                "logbook_cli.services.task_coordination.native_binding",
                return_value=binding,
            ),
            patch("logbook_cli.lifecycle.get", return_value={"value": "active"}),
            patch("logbook_cli.execution.require_delegation"),
            patch("logbook_cli.observation.action_lock", return_value=nullcontext()),
            patch(
                "logbook_cli.services.transport.herdr.control", return_value={}
            ) as host,
        ):
            from logbook_cli.services.readiness import require_ready

            with patch(
                "logbook_cli.services.readiness.require_ready",
                wraps=None if change_before_intent else require_ready,
            ):
                if change_before_intent:
                    host.side_effect = attempt_transport
                with self.assertRaises(LbError):
                    send_task(
                        root,
                        "log.md",
                        "task",
                        "binding",
                        "operation",
                        "execution-token",
                        "session",
                        "observation",
                        "message.md",
                    )
            if change_before_intent:
                host.assert_called_once()
            else:
                host.assert_not_called()
