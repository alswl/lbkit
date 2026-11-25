import unittest
from pathlib import Path
from unittest.mock import patch

from logbook_cli.document import next_task
from logbook_cli.lifecycle import compact, render
from logbook_cli.repository import markdown_document

ACTIVE = "> Status: 🚧 Active"
BLOCKER = "    - Blocker: Baseline input unavailable\n"


class StageSummaryTests(unittest.TestCase):
    def setUp(self):
        execution_read = patch(
            "logbook_cli.execution._read", return_value=(None, b"", None, None)
        )
        execution_read.start()
        self.addCleanup(execution_read.stop)

    def document(self, stage_one, stage_two, *, status=ACTIVE):
        root = Path("/example")
        body = (
            f"# Work\n\n{status}\n\n"
            f"## Stage 01 Prepare\n\n{stage_one}\n"
            f"## Stage 02 Verify\n\n{stage_two}"
        )
        return markdown_document(body.encode(), root / "log.md", root)

    def test_blocked_stage_stays_current_without_changing_next_task(self):
        doc = self.document(
            "- [/] Prepare input\n" + BLOCKER,
            "- [ ] Verify output\n    - Depends: a\n",
        )
        self.assertEqual(next_task(doc).text, "Verify output")
        self.assertEqual(compact(doc), f"{ACTIVE} · Stage 01 · Blocked")

    def test_blocked_stage_stays_current_when_an_independent_stage_is_active(self):
        doc = self.document("- [/] Prepare input\n" + BLOCKER, "- [/] Verify output\n")
        self.assertEqual(compact(doc), f"{ACTIVE} · Stage 01 · Blocked")

    def test_active_peer_keeps_the_current_stage_without_a_blocked_summary(self):
        doc = self.document(
            "- [/] Prepare input\n" + BLOCKER + "- [/] Prepare checksum\n",
            "- [ ] Verify output\n",
        )
        self.assertEqual(compact(doc), f"{ACTIVE} · Stage 01")

    def test_unblock_keeps_the_stage_and_completion_advances_it(self):
        for state, expected_stage in (("/", "Stage 01"), ("x", "Stage 02")):
            with self.subTest(state=state):
                doc = self.document(
                    f"- [{state}] Prepare input\n", "- [ ] Verify output\n"
                )
                self.assertEqual(compact(doc), f"{ACTIVE} · {expected_stage}")

    def test_non_active_lifecycle_and_manual_summary_keep_existing_behavior(self):
        blocked = "- [/] Prepare input\n" + BLOCKER
        pending = "- [ ] Verify output\n"
        ready = "> Status: 🛫 Ready"
        paused = "> Status: ⏸ Paused"
        manual = "> Status: Reviewed by the owner"
        self.assertEqual(
            compact(self.document(blocked, pending, status=ready)),
            f"{ready} · Stage 02",
        )
        self.assertEqual(
            compact(self.document(blocked, pending, status=paused)), paused
        )
        doc = self.document(blocked, pending, status=manual)
        self.assertEqual(render(doc), doc.text)
