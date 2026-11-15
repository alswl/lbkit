"""Instance publication is a single-document operation, not sidecar creation."""

import unittest
from pathlib import Path
from unittest.mock import patch

from logbook_cli.services import workflows
from logbook_cli.services.common import Result


class InstancePublicationTests(unittest.TestCase):
    def test_instance_returns_provenance_without_creating_old_state(self):
        content = "# Run\n\n## Stage 01 Build\n- [ ] Build feature\n"
        provenance = {
            "workflow": "workflows/example/docs/example.md",
            "template_digest": "digest",
            "inputs": {},
        }
        with (
            patch.object(workflows, "template"),
            patch.object(workflows, "lifecycle", return_value="ready"),
            patch.object(
                workflows,
                "render",
                return_value=Result(
                    {
                        "content": content,
                        "provenance": provenance,
                        "next": "bind companions",
                    }
                ),
            ),
            patch.object(workflows, "root_path", return_value=Path("/repo")),
            patch.object(Path, "is_symlink", return_value=False),
            patch.object(Path, "is_dir", return_value=True),
            patch.object(Path, "exists", return_value=False),
            patch.object(Path, "resolve", lambda path: path),
            patch.object(workflows, "check", return_value=[]),
            patch("logbook_cli.storage.create_bytes") as create,
            patch.object(workflows, "write_bytes") as old_writer,
        ):
            result = workflows.instantiate(
                "/repo", "example", "input.json", "token", "docs/run.md", False
            )
        create.assert_called_once_with(
            Path("/repo/docs/run.md"), content.encode(), False
        )
        old_writer.assert_not_called()
        self.assertEqual(result.value["provenance"], provenance)
        self.assertTrue(result.value["initialization_required"])
        self.assertNotIn("state_path", result.value)
