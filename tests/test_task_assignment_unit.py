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
