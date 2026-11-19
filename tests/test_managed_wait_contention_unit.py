import asyncio
from time import monotonic
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, patch

from herdr_fixtures import target

from logbook_cli import wait_state
from logbook_cli.document import EXIT_REFUSED, LbError
from logbook_cli.services import agent_wait
from logbook_cli.storage import WriterBusy


class ManagedWaitContentionTest(IsolatedAsyncioTestCase):
    async def test_retries_only_the_same_transiently_rejected_commit(self):
        committed = object()
        attempt = Mock(side_effect=[WriterBusy("writer_busy: fixture lock"), committed])
        result = await agent_wait.commit_with_retry(
            attempt, monotonic() + 2, agent_wait.Interruption(), "sample not saved"
        )
        self.assertIs(result, committed)
        self.assertEqual(attempt.call_count, 2)

    async def test_reports_persistent_contention_and_interruption(self):
        for interrupted in (False, True):
            with self.subTest(interrupted=interrupted):
                interruption = agent_wait.Interruption()
                if interrupted:
                    asyncio.get_running_loop().call_soon(interruption.interrupt, 15)
                attempt = Mock(side_effect=WriterBusy("writer_busy: fixture lock"))
                boundary = "interrupted" if interrupted else "deadline elapsed"
                with self.assertRaisesRegex(
                    LbError, f"sample not saved .*{boundary}"
                ) as caught:
                    await agent_wait.commit_with_retry(
                        attempt,
                        monotonic() + (2 if interrupted else 0.04),
                        interruption,
                        "sample not saved",
                    )
                self.assertEqual(caught.exception.code, EXIT_REFUSED)
                self.assertGreaterEqual(attempt.call_count, 1)
                if interrupted:
                    self.assertEqual(attempt.call_count, 1)

    async def test_propagates_non_lock_refusals_without_retrying(self):
        for message in (
            "version_conflict: monitoring changed",
            "invalid_transition: listener generation changed",
            "writer_busy: an untyped error",
        ):
            with self.subTest(message=message):
                refused = LbError(message, EXIT_REFUSED)
                attempt = Mock(side_effect=refused)
                with self.assertRaises(LbError) as caught:
                    await agent_wait.commit_with_retry(
                        attempt,
                        monotonic() + 2,
                        agent_wait.Interruption(),
                        "sample not saved",
                    )
                self.assertIs(caught.exception, refused)
                attempt.assert_called_once_with()

    async def test_batch_end_waits_for_an_already_sampled_target(self):
        targets = [target(1), target(2)]
        contexts = [wait_state.initial(item) for item in targets]
        entered = asyncio.Event()
        released = asyncio.Event()
        committed = []

        async def sample(index, cursor, events):
            self.assertEqual(cursor["sequence"], 1)
            self.assertEqual(len(events), 1)
            if index == 0:
                entered.set()
                await released.wait()
            else:
                await entered.wait()
                asyncio.get_running_loop().call_later(0.02, released.set)
            committed.append(index)

        with (
            patch.object(
                agent_wait.herdr, "invoke_bounded", AsyncMock(return_value={})
            ),
            patch.object(agent_wait.herdr, "scope_machine", return_value="local"),
            patch.object(
                agent_wait.herdr,
                "binding_observation",
                side_effect=lambda binding, pane, agent: {
                    "binding": binding,
                    "state": "idle",
                },
            ),
            patch.object(
                agent_wait.claude_questions,
                "observe_native",
                AsyncMock(return_value=None),
            ),
        ):
            result = await agent_wait.observe_batch(
                targets, contexts, [], [], 2, sample, agent_wait.Interruption()
            )
        self.assertEqual(committed, [1, 0])
        self.assertEqual(len(result.value["events"]), 2)
        self.assertEqual(result.code, 0)
