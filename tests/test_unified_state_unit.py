import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from logbook_cli import unified
from logbook_cli.document import LbError
from logbook_cli.repository import (
    markdown_document,
    source_digest,
)
from logbook_cli.services import dependencies, dependency_transaction


class UnifiedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.log = self.root / "work.md"
        self.log.write_text("# Work\n## Stage 1\n")

    def test_initialize_replay_and_conflicting_identity(self):
        first = unified.initialize(self.root, self.log, "work", [], False)
        self.assertTrue(first["changed"])
        self.assertFalse(
            unified.initialize(self.root, self.log, "work", [], False)["changed"]
        )
        other = self.root / "other.md"
        other.write_text("# Other\n")
        with self.assertRaises(LbError):
            unified.initialize(self.root, other, "work", [], False)

    def test_dry_run_does_not_create_directory(self):
        unified.initialize(self.root, self.log, "work", [], True)
        self.assertFalse((self.root / "lb").exists())

    def test_run_dependencies_follow_only_the_published_authority(self):
        self.log.write_text(
            "# Work\n## Stage 1\n"
            "- [ ] First\n    <!-- lb-task first -->\n"
            "- [ ] Next\n    <!-- lb-task next -->\n    - Depends: first\n"
        )
        doc = markdown_document(self.log.read_bytes(), self.log, self.root)
        path = self.root / "lb/work.json"
        path.parent.mkdir()
        sidecar = dependencies.sidecar(path)
        run = {"identity": {"run_id": "run"}}
        sidecar.write_bytes(
            unified.encode(dependencies.envelope("run", {"first": [], "next": []}))
        )
        self.assertEqual(dependencies.load(doc, path, run)["next"], ["first"])
        run["dependency_source"] = sidecar.name
        self.assertEqual(dependencies.load(doc, path, run), {"first": [], "next": []})
        sidecar.unlink()
        with self.assertRaisesRegex(LbError, "unavailable"):
            dependencies.load(doc, path, run)

    def test_dependency_file_checks_identity_endpoints_order_and_cycles(self):
        graph = {"release": ["qa", "build"], "qa": [], "build": []}
        body = unified.encode(dependencies.envelope("run", graph))
        self.assertEqual(dependencies.decode(body, "run", set(graph)), graph)
        for run_id, known in (("other-run", set(graph)), ("run", {"release", "build"})):
            with self.subTest(run_id=run_id, known=known):
                with self.assertRaises(LbError):
                    dependencies.decode(body, run_id, known)
        for invalid in (
            {"a": ["a"]},
            {"a": ["b"], "b": ["a"]},
            {"a": ["b", "b"], "b": []},
            {"a": ["missing"]},
        ):
            with self.subTest(graph=invalid), self.assertRaises(LbError):
                dependencies.validate(invalid)

    def test_dependency_cutover_reuses_staged_sidecar_and_drops_projected_edges(self):
        data = (
            b"# Work\n## Stage 1\n"
            b"- [ ] First\n    <!-- lb-task first -->\n"
            b"- [ ] Next\n    <!-- lb-task next -->\n    - Depends: first\n"
        )
        doc = markdown_document(data, self.log, self.root)
        path = self.root / "lb/work.json"
        path.parent.mkdir()
        run = {
            "identity": {"run_id": "run", "log_path": "work.md"},
            "documents": {"work.md": {"tasks": {"next": {"dependencies": ["first"]}}}},
        }
        sidecar = dependencies.sidecar(path)
        graph = {"first": [], "next": ["first"]}
        sidecar.write_bytes(unified.encode(dependencies.envelope("run", graph)))

        with patch.object(dependencies, "replace_bytes_at") as replace:
            dependencies.stage_cutover(doc, path, run)
        replace.assert_not_called()
        self.assertEqual(run["dependency_source"], sidecar.name)
        self.assertEqual(run["documents"]["work.md"]["tasks"]["next"], {})

    def test_dependency_recovery_checks_token_and_preserves_subsequent_edits(self):
        from contextlib import nullcontext

        before = (
            b"# Work\n## Stage 1\n"
            b"- [ ] First\n    <!-- lb-task first -->\n"
            b"- [ ] Next\n    <!-- lb-task next -->\n    - Depends: first\n"
        )
        after = before.replace(b"lb-task first -->", b"lb-task replacement -->")
        run = self.root / "lb/work.json"
        run.parent.mkdir()
        sidecar = dependencies.sidecar(run)
        journal = dependency_transaction.journal_for(run)
        before_graph = unified.encode(
            dependencies.envelope("run", {"first": [], "next": ["first"]})
        )
        after_graph = dependencies.envelope("run", {"next": ["replacement"], "replacement": []})
        self.log.write_bytes(after)
        sidecar.write_bytes(before_graph)
        journal.write_bytes(unified.encode({
            "run_id": "run",
            "document_before": source_digest(before),
            "graph_before": source_digest(before_graph),
            "document": after.decode(),
            "graph": after_graph,
        }))
        record = {
            "identity": {"run_id": "run", "log_path": "work.md"},
            "dependency_source": sidecar.name,
        }
        with (
            patch.object(unified, "writer", return_value=nullcontext()),
            patch.object(unified, "locate", return_value=(run, record)),
        ):
            preview = dependency_transaction.recover(self.root, self.log, None, True)
            with self.assertRaisesRegex(LbError, "version_token"):
                dependency_transaction.recover(self.root, self.log, "stale", False)
            self.log.write_bytes(after + b"\nuser edit\n")
            with self.assertRaisesRegex(LbError, "subsequent edit"):
                dependency_transaction.recover(self.root, self.log, preview["version_token"], False)
            self.log.write_bytes(after)
            self.assertTrue(dependency_transaction.recover(
                self.root, self.log, preview["version_token"], False
            )["recovered"])
        self.assertFalse(journal.exists())
        self.assertEqual(sidecar.read_bytes(), unified.encode(after_graph))
        self.assertEqual(self.log.read_bytes(), after)

    def test_malformed_and_old_state_refused(self):
        (self.root / "lb").mkdir()
        old = self.root / "lb/work.md.json"
        old.write_text("{}")
        with self.assertRaises(LbError):
            unified.initialize(self.root, self.log, "work", [], False)
        old.unlink()
        (self.root / "lb/work.json").write_text("{")
        with self.assertRaises(LbError):
            unified.initialize(self.root, self.log, "work", [], False)

    def test_publish_failure_keeps_previous_file(self):
        unified.initialize(self.root, self.log, "work", [], False)
        path = self.root / "lb/work.json"
        before = path.read_bytes()
        value = unified.read(path)
        value["documents"]["work.md"] = {"source_digest": "new"}
        with patch(
            "logbook_cli.storage.replace_bytes_at", side_effect=OSError("disk failed")
        ):
            with self.assertRaises(OSError):
                unified.publish(path, value)
        self.assertEqual(before, path.read_bytes())

    def test_sync_replaces_projection_without_discarding_nested_history(self):
        from contextlib import nullcontext
        from copy import deepcopy

        from logbook_cli.repository import sync_document

        prior = {
            "documents": {
                "work.md": {
                    "source_digest": "old",
                    "stages": ["Old"],
                    "tasks": {},
                    "legacy_metadata": {
                        "task": {"old": {"decision": "Earlier decision"}},
                        "task-archive": {"archived": {"id": "archived"}},
                        "link-verification": {"observation": {"outcome": "verified"}},
                    },
                },
                "other.md": {"source_digest": "other"},
            },
            "identity": {"run_id": "sample"},
            "execution": {"facts": [{"kind": "submission"}]},
            "monitoring": {"targets": {"target": {"cursor": 10}}},
        }
        value = deepcopy(prior)
        with (
            patch("logbook_cli.unified.writer", return_value=nullcontext()),
            patch(
                "logbook_cli.unified.locate",
                return_value=(self.root / "lb/work.json", value),
            ),
            patch("logbook_cli.unified.publish_run") as publish,
        ):
            self.assertTrue(sync_document(self.root, self.log, dry_run=True)["changed"])
            publish.assert_not_called()
            self.assertEqual(value, prior)
            self.assertTrue(sync_document(self.root, self.log)["changed"])
            publish.assert_called_once()
            self.assertFalse(sync_document(self.root, self.log)["changed"])
        self.assertEqual(value["documents"]["work.md"]["stages"], ["Stage 1"])
        value["documents"]["work.md"]["stages"] = ["Old"]
        value["documents"]["work.md"]["source_digest"] = "old"
        self.assertEqual(value, prior)

    def test_read_document_loads_nested_history_for_its_own_path(self):
        from logbook_cli.repository import read_document

        retained = {"task-archive": {"retired": {"id": "retired"}}}
        value = {
            "documents": {
                "work.md": {"legacy_metadata": retained},
                "other.md": {
                    "legacy_metadata": {"task": {"another": {"decision": "Other"}}}
                },
            },
            "identity": {"run_id": "sample"},
        }
        target = self.root / "lb/work.json"
        with patch("logbook_cli.unified.locate", return_value=(target, value)):
            doc = read_document(self.root, self.log)
        self.assertEqual(doc.legacy_metadata, retained)
        self.assertEqual(doc.metadata["task-archive"], retained["task-archive"])
        self.assertEqual(doc.state_path, target)
