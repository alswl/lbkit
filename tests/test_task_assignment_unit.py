import unittest

from logbook_cli.document import LbError
from logbook_cli.services.task_coordination import assign_value, bind_value


class AssignmentTests(unittest.TestCase):
    def test_reassignment_preserves_binding_history(self):
        runtime = {}
        assign_value(
            runtime,
            {
                "subject": {"kind": "agent", "subject_id": "worker"},
                "basis": "authorized",
            },
        )
        runtime["current_binding_id"] = "old"
        assign_value(
            runtime,
            {"subject": {"kind": "agent", "subject_id": "worker"}, "basis": "retry"},
        )
        self.assertEqual(runtime["current_binding_id"], "old")
        assign_value(runtime, {"basis": "released"}, unassign=True)
        self.assertIsNone(runtime["current_binding_id"])
        self.assertEqual(runtime["assignment_revision"], 2)

    def test_binding_requires_matching_revision_and_is_immutable(self):
        runtime = {
            "assignee": {"kind": "agent", "subject_id": "worker"},
            "assignment_revision": 1,
            "execution_bindings": {},
        }
        with self.assertRaises(LbError):
            bind_value(runtime, {"id": "b", "assignment_revision": 0})

    def test_replaced_binding_cannot_be_reactivated_by_replaying_its_payload(self):
        runtime = {"assignee": {"kind": "agent", "subject_id": "worker"},
                   "assignment_revision": 1}
        original = {
            "id": "a", "assignment_revision": 1, "machine": "local",
            "session_id": "first", "adapter": "herdr",
            "runtime_locator": {"workspace_id": "w1", "tab_id": "w1:t1",
                                "pane_id": "w1:p1", "agent_id": "codex", "server": "default"},
            "work_context": {"repository_ref": None, "working_directory": "/example"},
            "input_ref": "fixture", "basis": "authorized", "observed_at": "2026-01-01T00:00:00Z",
        }
        bind_value(runtime, original)
        bind_value(runtime, original)
        bind_value(runtime, {**original, "id": "b", "session_id": "second"})
        with self.assertRaisesRegex(LbError, "new binding ID"):
            bind_value(runtime, original)
        self.assertEqual(runtime["current_binding_id"], "b")
        self.assertEqual(set(runtime["execution_bindings"]), {"a", "b"})
