"""Fixture controls must work before they can support feature Red assertions."""

import json
import os
import subprocess
import sys

from observation_fixtures import ObservationTest, receipt, target


class ObservationFixtureTest(ObservationTest):
    def spawn(self):
        process = subprocess.Popen(
            [sys.executable, str(self.base / "bin/herdr"), "question", "submit"],
            env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )

        def cleanup():
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=2)

        self.addCleanup(cleanup)
        return process

    def script_submission(self, barriers):
        self.script([{
            "argv": ["question", "submit"],
            "responses": [{"submission": "example-operation", "stdout": receipt(),
                           "barriers": barriers}],
        }])

    def test_builders_need_no_observation_module_or_runtime(self):
        self.identify()
        self.assertEqual(json.loads(self.configuration().read_text()), {"targets": [target()]})
        self.assertEqual(json.loads(self.evidence().read_text()), receipt())
        self.assertEqual(self.calls(), [])

    def test_submission_and_receipt_can_be_released_separately(self):
        before = self.barrier("before")
        after = self.barrier("after")
        self.script_submission({"before_submit": "before", "before_receipt": "after"})
        child = self.spawn()
        self.wait_checkpoint("before_submit")
        self.assertEqual(self.submission_count(), 0)
        os.write(before, b"1")
        self.wait_checkpoint("before_receipt")
        self.assertEqual(self.submission_count(), 1)
        self.assertIsNone(child.poll())
        os.write(after, b"1")
        stdout, stderr = child.communicate(timeout=2)
        self.assertEqual(child.returncode, 0, stderr)
        self.assertEqual(json.loads(stdout), receipt())
        self.assertEqual(self.submission_count(), 1)

    def test_crash_after_submission_has_no_receipt(self):
        self.barrier("crash")
        self.script_submission({"after_submit": "crash"})
        child = self.spawn()
        self.wait_checkpoint("after_submit")
        self.assertEqual(self.submission_count(), 1)
        child.kill()
        stdout, _ = child.communicate(timeout=2)
        self.assertLess(child.returncode, 0)
        self.assertEqual(stdout, b"")
        self.assertEqual(self.submission_count(), 1)

    def test_crash_before_submission_sends_nothing(self):
        self.barrier("crash")
        self.script_submission({"before_submit": "crash"})
        child = self.spawn()
        self.wait_checkpoint("before_submit")
        child.kill()
        stdout, _ = child.communicate(timeout=2)
        self.assertEqual(stdout, b"")
        self.assertEqual(self.submission_count(), 0)

    def test_receipt_can_be_observed_before_process_exit(self):
        gate = self.barrier("receipt")
        self.script_submission({"after_receipt": "receipt"})
        child = self.spawn()
        self.wait_checkpoint("after_receipt")
        self.assertIsNone(child.poll())
        os.write(gate, b"1")
        stdout, stderr = child.communicate(timeout=2)
        self.assertEqual(child.returncode, 0, stderr)
        self.assertEqual(json.loads(stdout), receipt())
        self.assertEqual(self.submission_count(), 1)
