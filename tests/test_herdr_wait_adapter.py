"""Bounded child-call contract, separate from Herdr business/session controls."""

import asyncio
import os
import time
from unittest.mock import patch

from coordination_helpers import CoordinationTest

from logbook_cli.adapters import herdr
from logbook_cli.document import LbError


class HerdrWaitAdapterTest(CoordinationTest):
    def setUp(self):
        super().setUp()
        self.assertTrue(
            callable(getattr(herdr, "invoke_bounded", None)),
            "T039 bounded Herdr child-call helper is not implemented",
        )

    def invoke(self, *args, duration=0.3):
        async def run():
            return await herdr.invoke_bounded(
                "local",
                *args,
                deadline=time.monotonic() + duration,
                output_limit=256 * 1024,
            )

        with patch.dict(os.environ, self.env):
            return asyncio.run(run())

    def assert_children_reaped(self):
        for call in self.calls():
            if call["kind"] == "start":
                with self.assertRaises(ProcessLookupError):
                    os.kill(call["pid"], 0)

    def test_argument_arrays_preserve_literal_shell_characters(self):
        literal = "w1:p1; touch sentinel"
        self.script(
            [
                {
                    "argv": ["agent", "get", literal],
                    "responses": [{"stdout": {"ok": True}}],
                }
            ]
        )
        self.assertEqual(self.invoke("agent", "get", literal, duration=2), {"ok": True})
        self.assertFalse((self.root / "sentinel").exists())
        self.assertEqual(self.calls()[0]["argv"], ["agent", "get", literal])

    def test_oversized_stdout_is_refused_and_child_is_reaped(self):
        self.script(
            [{"argv": ["agent", "get"], "responses": [{"stdout_bytes": 1024 * 1024}]}]
        )
        with self.assertRaises(LbError):
            self.invoke("agent", "get", "w1:p1")
        self.assert_children_reaped()

    def test_oversized_stderr_is_refused_and_child_is_reaped(self):
        self.script(
            [{"argv": ["agent", "get"], "responses": [{"stderr_bytes": 1024 * 1024}]}]
        )
        with self.assertRaises(LbError):
            self.invoke("agent", "get", "w1:p1")
        self.assert_children_reaped()

    def test_malformed_json_is_unavailable(self):
        self.script([{"argv": ["agent", "get"], "responses": [{"stdout": "{bad"}]}])
        with self.assertRaises(LbError):
            self.invoke("agent", "get", "w1:p1")
        self.assert_children_reaped()

    def test_deadline_terminates_then_kills_unresponsive_owned_child(self):
        self.script(
            [
                {
                    "argv": ["agent", "wait"],
                    "responses": [{"delay": 20, "ignore_term": True}],
                }
            ]
        )
        started = time.monotonic()
        with self.assertRaises(LbError):
            self.invoke("agent", "wait", "w1:p1")
        self.assertLess(time.monotonic() - started, 2.8)
        self.assert_children_reaped()

    def test_expired_shared_deadline_does_not_spawn(self):
        with self.assertRaises(LbError):
            self.invoke("agent", "wait", "w1:p1", duration=-1)
        self.assertEqual(self.calls(), [])

    def test_cancellation_reaps_only_owned_child(self):
        self.script([{"argv": ["agent", "wait"], "responses": [{"delay": 20}]}])

        async def run():
            task = asyncio.create_task(
                herdr.invoke_bounded(
                    "local",
                    "agent",
                    "wait",
                    "w1:p1",
                    deadline=time.monotonic() + 10,
                    output_limit=256 * 1024,
                )
            )
            await asyncio.sleep(0.2)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task

        with patch.dict(os.environ, self.env):
            asyncio.run(run())
        self.assert_children_reaped()
        self.assertTrue(
            all(
                "close" not in c["argv"] and "stop" not in c["argv"]
                for c in self.calls()
            )
        )

    def test_repeated_cancellation_cannot_interrupt_child_cleanup(self):
        self.script(
            [
                {
                    "argv": ["agent", "wait"],
                    "responses": [
                        {"delay": 20, "ignore_term": True, "record_ready": True}
                    ],
                }
            ]
        )

        async def wait_for(kind):
            async with asyncio.timeout(2):
                while not any(row["kind"] == kind for row in self.calls()):
                    await asyncio.sleep(0.01)

        async def run():
            task = asyncio.create_task(
                herdr.invoke_bounded(
                    "local",
                    "agent",
                    "wait",
                    "w1:p1",
                    deadline=time.monotonic() + 10,
                    output_limit=256 * 1024,
                )
            )
            try:
                await wait_for("ready")
                task.cancel()
                await wait_for("signal")
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task
                self.assert_children_reaped()
            finally:
                # A failing regression must still reclaim its own fixture.
                for row in self.calls():
                    if row["kind"] == "start":
                        try:
                            os.kill(row["pid"], 9)
                        except ProcessLookupError:
                            pass

        with patch.dict(os.environ, self.env):
            asyncio.run(run())
