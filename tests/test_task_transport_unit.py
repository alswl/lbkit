import unittest

from logbook_cli.document import LbError
from logbook_cli.services.transport import task_send_guard


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

    def test_submitted_old_binding_does_not_block_new_instruction_binding(self):
        ex = {
            "operations": {
                "old": {
                    "outcome": "submitted",
                    "request": {"task_id": "a", "binding_id": "old"},
                }
            }
        }
        self.assertIsNone(
            task_send_guard(ex, "a", "new-op", {"task_id": "a", "binding_id": "new"})
        )
