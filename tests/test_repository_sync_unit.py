import unittest
from pathlib import Path
from unittest.mock import patch

from logbook_cli import repository
from logbook_cli.document import LbError


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.data = b"# Work\n## Stage 1\n- [ ] Task\n    <!-- lb-task a -->\n"
        self.value = {
            "documents": {},
            "execution": {"tasks": {"a": {"assignee": "owner"}}},
        }

    def test_sync_changes_only_projection_and_replay_is_noop(self):
        with (
            patch.object(repository, "root_path", return_value=Path("/repo")),
            patch.object(repository, "safe_path", return_value=Path("/repo/work.md")),
            patch.object(repository.unified, "writer"),
            patch.object(
                repository.unified,
                "locate",
                return_value=(Path("/repo/lb/work.json"), self.value),
            ),
            patch.object(Path, "read_bytes", return_value=self.data),
            patch.object(repository.unified, "publish_run") as publish,
        ):
            result = repository.sync_document("/repo", "work.md")
            self.assertEqual(result["sync_status"], "synced")
            self.assertEqual(self.value["execution"]["tasks"]["a"]["assignee"], "owner")
            self.assertTrue(result["changed"])
            publish.reset_mock()
            self.assertFalse(repository.sync_document("/repo", "work.md")["changed"])
            publish.assert_not_called()

    def test_failure_does_not_publish_or_remove_runtime(self):
        with (
            patch.object(repository, "root_path", return_value=Path("/repo")),
            patch.object(repository, "safe_path", return_value=Path("/repo/work.md")),
            patch.object(repository.unified, "writer"),
            patch.object(
                repository.unified,
                "locate",
                return_value=(Path("/repo/lb/work.json"), self.value),
            ),
            patch.object(
                Path, "read_bytes", return_value=b"# Work\n## Stage 1\n- [ ] No ID\n"
            ),
            patch.object(repository.unified, "publish_run") as publish,
        ):
            with self.assertRaises(LbError):
                repository.sync_document("/repo", "work.md")
            publish.assert_not_called()
            self.assertEqual(self.value["documents"], {})

    def test_snapshot_modified_during_sync_returns_stale(self):
        with (
            patch.object(repository, "root_path", return_value=Path("/repo")),
            patch.object(repository, "safe_path", return_value=Path("/repo/work.md")),
            patch.object(repository.unified, "writer"),
            patch.object(
                repository.unified,
                "locate",
                return_value=(Path("/repo/lb/work.json"), self.value),
            ),
            patch.object(
                Path, "read_bytes", side_effect=[self.data, self.data + b"changed"]
            ),
            patch.object(repository.unified, "publish_run"),
        ):
            self.assertEqual(
                repository.sync_document("/repo", "work.md")["sync_status"], "stale"
            )
