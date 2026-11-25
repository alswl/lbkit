from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from logbook_cli.document import LbError
from logbook_cli.services.preflight_observations import Cache, Observation


class PreflightCacheTests(TestCase):
    def setUp(self):
        scratch = self.enterContext(TemporaryDirectory())
        self.enterContext(
            patch(
                "logbook_cli.services.preflight_observations.tempfile.gettempdir",
                return_value=scratch,
            )
        )
        self.workspace = Path(scratch) / "workspace"
        self.run_id = "a" * 32
        self.cache = Cache(self.workspace, self.run_id)
        self.path = Path(scratch).joinpath(*self.cache.parts, self.cache.name)
        self.now = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
        self.row = Observation(
            task_id="task",
            check_id="build",
            subject_id="developer",
            environment_ref="current-session",
            scope_ref="current-scope",
            candidate_ref="candidate",
            check_ref="approved-check",
            response_ref="reply-original",
            source="native reply",
            status="passed",
            checked_at=self.now.isoformat(),
            expires_at=(self.now + timedelta(minutes=5)).isoformat(),
        )

    def lookup(self, row=None, cache=None, now=None):
        row = row or self.row
        return (cache or self.cache).get(
            row.key,
            scope_ref=row.scope_ref,
            candidate_ref=row.candidate_ref,
            check_ref=row.check_ref,
            now=now or self.now,
        )

    def test_only_current_environment_candidate_and_scope_are_reused(self):
        self.assertTrue(self.cache.record(self.row, now=self.now))
        self.assertEqual(
            self.lookup(cache=Cache(self.workspace, self.run_id)), self.row
        )
        for field in ("environment_ref", "task_id", "scope_ref", "candidate_ref", "check_ref"):
            with self.subTest(field=field):
                self.assertIsNone(self.lookup(replace(self.row, **{field: "other"})))
        self.assertIsNone(self.lookup(cache=Cache(self.workspace, "b" * 32)))
        self.assertIsNone(
            self.lookup(cache=Cache(self.workspace.with_name("other"), self.run_id))
        )
        self.assertIsNone(self.lookup(now=self.now + timedelta(minutes=5)))

    def test_keep_unrelated_results_and_reject_late_or_replayed_results(self):
        reviewer = replace(self.row, subject_id="reviewer")
        self.cache.record(self.row, now=self.now)
        self.cache.record(reviewer, now=self.now)
        later = self.now + timedelta(minutes=1)
        replay = replace(
            self.row, expires_at=(later + timedelta(minutes=9)).isoformat()
        )
        self.assertFalse(self.cache.record(replay, now=later))
        newer = replace(
            reviewer,
            checked_at=later.isoformat(),
            response_ref="reply-failed",
            status="failed",
        )
        self.assertTrue(self.cache.record(newer, now=later))
        self.assertFalse(
            self.cache.record(replace(reviewer, response_ref="late"), now=later)
        )
        self.assertEqual(self.lookup(reviewer, now=later), newer)
        self.assertEqual(self.lookup(), self.row)

    def test_missing_or_corrupt_cache_can_be_repopulated(self):
        self.assertIsNone(self.lookup())
        self.assertFalse(self.path.parent.exists())
        self.cache.record(self.row, now=self.now)
        self.path.write_text("incomplete")
        self.assertIsNone(self.lookup())
        self.assertTrue(self.cache.record(self.row, now=self.now))
        self.path.unlink()
        self.assertIsNone(self.lookup())

    def test_refuse_symlink_and_non_private_paths(self):
        self.cache.record(self.row, now=self.now)
        self.path.chmod(0o644)
        self.assertIsNone(self.lookup())
        with self.assertRaises(LbError):
            self.cache.record(self.row, now=self.now)
        self.path.unlink()
        unrelated = self.path.with_name("unrelated")
        unrelated.write_text("leave intact")
        self.path.symlink_to(unrelated)
        self.assertIsNone(self.lookup())
        with self.assertRaises(LbError):
            self.cache.record(self.row, now=self.now)
        self.assertEqual(unrelated.read_text(), "leave intact")
