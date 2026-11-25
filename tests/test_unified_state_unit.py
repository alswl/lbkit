import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from logbook_cli import unified
from logbook_cli.document import LbError
from logbook_cli.repository import edit_document, markdown_document, read_document
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

    def test_dependency_cutover_can_reuse_an_interrupted_stage(self):
        from logbook_cli.services.route_scope import route_scope

        self.log.write_text(
            "# Work\n## Stage 1\n"
            "- [ ] First\n    <!-- lb-task first -->\n"
            "- [ ] Next\n    <!-- lb-task next -->\n    - Depends: first\n"
        )
        unified.initialize(self.root, self.log, "work", [])
        doc = read_document(self.root, self.log)
        before = route_scope(doc)
        path = self.root / "lb/work.json"
        with unified.writer(self.root, self.log), patch.object(
            unified, "publish", side_effect=OSError("Run publication interrupted")
        ):
            with self.assertRaises(OSError):
                unified.publish_run(self.root, path, unified.read(path))
        self.assertNotIn("dependency_source", unified.read(path))
        with unified.writer(self.root, self.log):
            staged = unified.read(path)
            unified.publish_run(self.root, path, staged)
        current = read_document(self.root, self.log)
        self.assertEqual(current.task_dependency_graph, {"first": [], "next": ["first"]})
        self.assertEqual(current.data, doc.data)
        self.assertEqual(route_scope(current), before)
        dependencies.sidecar(path).write_bytes(unified.encode(dependencies.envelope(
            staged["identity"]["run_id"], {"first": [], "next": []}
        )))
        changed = route_scope(read_document(self.root, self.log))
        self.assertNotEqual(changed["route_ref"], before["route_ref"])
        self.assertNotEqual(changed["task_scopes"]["next"], before["task_scopes"]["next"])
        self.assertEqual(changed["task_scopes"]["first"], before["task_scopes"]["first"])
        dependencies.sidecar(path).unlink()
        with self.assertRaisesRegex(LbError, "dependency file unavailable"):
            read_document(self.root, self.log)

    def test_interrupted_task_replacement_requires_recovery_before_admission(self):
        before = (
            "# Work\n## Stage 1\n"
            "- [ ] First\n    <!-- lb-task first -->\n"
            "- [ ] Next\n    <!-- lb-task next -->\n    - Depends: first\n"
        )
        after = before.replace("lb-task first -->", "lb-task replacement -->")
        graph = {"next": ["replacement"], "replacement": []}
        self.log.write_text(before)
        unified.initialize(self.root, self.log, "work", [])
        run = self.root / "lb/work.json"
        with unified.writer(self.root, self.log):
            unified.publish_run(self.root, run, unified.read(run))
        doc = read_document(self.root, self.log)
        before_graph = dependencies.sidecar(run).read_bytes()
        self.assertTrue(edit_document(doc, after, True, dependency_graph=graph)["sync_required"])
        self.assertFalse(dependency_transaction.present(run))
        original_replace = dependency_transaction.replace_file

        def interrupt(path, new, old):
            if path == dependencies.sidecar(run):
                raise OSError("interrupted after publishing Markdown")
            original_replace(path, new, old)

        with patch.object(dependency_transaction, "replace_file", side_effect=interrupt):
            with self.assertRaisesRegex(OSError, "interrupted"):
                edit_document(doc, after, dependency_graph=graph)
        self.assertEqual(self.log.read_text(), after)
        self.assertEqual(dependencies.sidecar(run).read_bytes(), before_graph)
        with self.assertRaisesRegex(LbError, "unfinished dependency transaction"):
            read_document(self.root, self.log)

        preview = dependency_transaction.recover(self.root, self.log, None, True)
        with self.assertRaisesRegex(LbError, "version_token"):
            dependency_transaction.recover(self.root, self.log, "stale", False)
        self.log.write_text(after + "\nuser edit\n")
        with self.assertRaisesRegex(LbError, "subsequent edit"):
            dependency_transaction.recover(self.root, self.log, preview["version_token"], False)
        self.log.write_text(after)
        self.assertTrue(dependency_transaction.recover(
            self.root, self.log, preview["version_token"], False
        )["recovered"])
        self.assertFalse(dependency_transaction.present(run))
        current = read_document(self.root, self.log)
        self.assertEqual(current.task_dependency_graph, graph)
        self.assertEqual(current.data.decode(), after)

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
