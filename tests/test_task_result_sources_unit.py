import unittest

from logbook_cli.document import LbError
from logbook_cli.services.task_coordination import result_value


class ResultSourceTests(unittest.TestCase):
    def test_original_binding_and_replay(self):
        runtime = {"execution_bindings": {"old": {}}, "result_sources": {}}
        payload = {
            "ref": "result.txt",
            "source": {"binding_id": "old"},
            "observed_at": "2026-11-15T00:00:00Z",
        }
        result_value(runtime, ["result.txt"], payload)
        result_value(runtime, ["result.txt"], payload)
        self.assertIsNone(runtime["result_sources"]["result.txt"]["version_ref"])
        self.assertEqual(len(runtime["result_sources"]), 1)

    def test_cross_task_and_missing_ref_rejected(self):
        runtime = {"execution_bindings": {}, "result_sources": {}}
        with self.assertRaises(LbError):
            result_value(
                runtime,
                ["a"],
                {
                    "ref": "a",
                    "source": {"binding_id": "foreign"},
                    "observed_at": "2026-11-15T00:00:00Z",
                },
            )
        with self.assertRaises(LbError):
            result_value(
                runtime,
                [],
                {
                    "ref": "a",
                    "source": {
                        "kind": "human",
                        "subject_id": "reviewer",
                        "basis": "reported",
                    },
                    "observed_at": "2026-11-15T00:00:00Z",
                },
            )
