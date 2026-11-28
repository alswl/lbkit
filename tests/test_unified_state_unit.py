import fcntl
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from logbook_cli import execution, legacy_migration, state, unified
from logbook_cli.document import LbError
from logbook_cli.repository import (
    markdown_document,
    source_digest,
)
from logbook_cli.services import dependencies, dependency_transaction
from logbook_cli.storage import WriterBusy

OVERDEEP_SIDECAR = (
    b'{"format":"lb-document-state","documents":{"docs/archive.md":{"history":'
    + b"[" * 100_000 + b"0" + b"]" * 100_000 + b"}}}"
)


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

    def test_execution_writer_binds_captain_only_before_history(self):
        doc = markdown_document(self.log.read_bytes(), self.log, self.root)
        path = self.root / "lb/work.json"
        old = {"captain": "captain", "facts": [], "operations": []}
        for section, actor, allowed, changed in (
            ({}, "coordinator", True, True),
            ({}, "captain", True, True),
            ({"captain": "captain"}, "coordinator", False, False),
            ({"captain": "coordinator"}, "coordinator", True, False),
            ({"operations": {"existing": {}}}, "coordinator", False, False),
            ({"facts": [{"id": "historical"}]}, "coordinator", False, False),
        ):
            with self.subTest(section=section, actor=actor):
                runtime = {"facts": [], "operations": {}} | section
                envelope = {"identity": {}, "execution": runtime}
                raw = unified.section_content(envelope, "execution")
                token = hashlib.sha256(raw).hexdigest()
                observed = {**old, "captain": runtime.get("captain", "captain")}
                with (
                    patch.object(execution, "read", return_value=(path, raw, observed)),
                    patch.object(unified, "locate", return_value=(path, envelope)),
                    patch.object(unified, "publish_run") as publish,
                ):
                    args = (doc, "work", {**observed, "captain": actor}, token, False)
                    if allowed:
                        result = execution.write(*args, bind_captain=True)
                        self.assertEqual(result["changed"], changed)
                        self.assertEqual(runtime["captain"], actor)
                        self.assertEqual(publish.called, changed)
                    else:
                        with self.assertRaisesRegex(LbError, "identity already established"):
                            execution.write(*args, bind_captain=True)
                        publish.assert_not_called()

    def test_dry_run_does_not_create_directory(self):
        unified.initialize(self.root, self.log, "work", [], True)
        self.assertFalse((self.root / "lb").exists())

    def test_project_keys_are_the_same_from_host_and_project_roots(self):
        project = self.root / "project"
        project.mkdir()
        (project / "mind.yaml").touch()
        log = self.log.rename(project / "work.md")
        companion = project / "thinking.md"
        companion.touch()
        host = unified.initialize(
            self.root, log, "work", ["project/thinking.md"], dry_run=True
        )
        local = unified.initialize(
            project, log, "work", ["thinking.md"], dry_run=True
        )
        self.assertEqual(host["state"]["identity"]["document_paths"], ["thinking.md", "work.md"])
        self.assertEqual(
            host["state"]["identity"]["document_paths"],
            local["state"]["identity"]["document_paths"],
        )

    def test_locate_existing_project_keys_from_either_root(self):
        project = self.root / "project"
        (project / "lb").mkdir(parents=True)
        (project / "mind.yaml").touch()
        log = self.log.rename(project / "work.md")
        companion = project / "thinking.md"
        companion.touch()
        run = {
            "format": unified.FORMAT,
            "identity": {
                "run_id": "a" * 32, "log_path": "work.md",
                "document_paths": ["thinking.md", "work.md"],
            },
            "documents": {},
            "execution": {"operations": {}, "tasks": {}, "facts": []},
            "monitoring": None,
        }
        target = project / "lb/work.json"
        target.write_bytes(unified.encode(run))
        for root in (self.root, project):
            for document in (log, companion):
                with self.subTest(root=root, document=document):
                    self.assertEqual(unified.locate(root, document), (target, run))

    def test_initialize_refuses_companions_in_another_project(self):
        project = self.root / "project"
        nested = project / "nested"
        nested.mkdir(parents=True)
        (project / "mind.yaml").touch()
        (nested / "mind.yaml").touch()
        (nested / "thinking.md").touch()
        log = self.log.rename(project / "work.md")
        (self.root / "thinking.md").touch()
        for name in ("thinking.md", "project/nested/thinking.md"):
            with self.subTest(name=name), self.assertRaises(LbError) as exc:
                unified.initialize(self.root, log, "work", [name])
            for part in ("--document", name, str(self.root), "outside the Logbook project"):
                self.assertIn(part, str(exc.exception))
        self.assertFalse((project / "lb").exists())

    def legacy_sidecar(self, relative, identity):
        path = state.path_for(self.root / relative, self.root)
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(state.encode_file({
            relative: {"document": {"identity": {"id": "identity", "uuid": identity}}}
        }))
        return path

    def test_initialize_ignores_observations_owned_by_another_document(self):
        identity = "a" * 32
        old = self.legacy_sidecar("docs/archive.md", identity)
        folder = old.parent / "observations"
        folder.mkdir()
        observation = folder / (identity + ".json")
        observation.write_bytes(b"opaque legacy event history\n")
        listener = observation.with_suffix(".listener")
        listener.write_bytes(b"listener\n")
        action = observation.with_suffix(".action-" + "b" * 64)
        action.write_bytes(b"action\n")
        retained = old.with_name("retained.json")
        retained.write_bytes(state.encode_file({"docs/older.md": {"document": {}}}))
        historical = {
            path: path.read_bytes() for path in (old, observation, listener, action, retained)
        }

        with listener.open("rb") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            preview = unified.initialize(self.root, self.log, "work", [], True)
            self.assertTrue(preview["changed"])
            self.assertFalse((old.parent / "work.json").exists())
            self.assertFalse((old.parent / ".lock").exists())
            applied = unified.initialize(self.root, self.log, "work", [], False)
        self.assertIsNone(applied["state"]["monitoring"])
        self.assertFalse(unified.initialize(self.root, self.log, "work", [])["changed"])
        self.assertEqual(historical, {path: path.read_bytes() for path in historical})

    def assert_init_refused(self, message):
        for dry_run in (True, False):
            with self.subTest(dry_run=dry_run), self.assertRaisesRegex(LbError, message):
                unified.initialize(self.root, self.log, "work", [], dry_run)
        self.assertFalse((self.root / "lb/work.json").exists())
        self.assertFalse((self.root / "lb/.lock").exists())

    def test_initialize_refuses_own_sidecar_and_path_keyed_observation(self):
        identity = "a" * 32
        own = self.legacy_sidecar("work.md", identity)
        folder = own.parent / "observations"
        folder.mkdir()
        observation = folder / (identity + ".json")
        observation.write_bytes(b"past observations")
        before = own.read_bytes()
        self.assert_init_refused("old layout conflict")
        self.assertEqual(own.read_bytes(), before)
        self.assertEqual(observation.read_bytes(), b"past observations")

        own.unlink()
        path_keyed = observation.rename(folder / "work.md.json")
        self.assert_init_refused("old observations layout conflict")
        self.assertEqual(path_keyed.read_bytes(), b"past observations")

    def test_initialize_refuses_unowned_misfiled_and_duplicate_uuid(self):
        identity = "a" * 32
        folder = self.root / "lb/observations"
        folder.mkdir(parents=True)
        observation = folder / (identity + ".json")
        observation.write_bytes(b"past observations")
        self.assert_init_refused("old observations layout conflict")

        owner = self.legacy_sidecar("docs/archive.md", identity)
        misplaced = owner.rename(owner.with_name("wrong.md.json"))
        self.assert_init_refused("old observations layout conflict")
        retained = misplaced.rename(owner.with_name("retained.json"))
        self.assert_init_refused("old observations layout conflict")
        retained.rename(owner)
        duplicate = self.legacy_sidecar("docs/duplicate.md", identity)
        before = {path: path.read_bytes() for path in (observation, owner, duplicate)}
        self.assert_init_refused("old observations layout conflict")
        self.assertEqual(before, {path: path.read_bytes() for path in before})

    def test_initialize_refuses_renamed_duplicate_observation_owner(self):
        identity = "a" * 32
        owner = self.legacy_sidecar("docs/archive.md", identity)
        observed = owner.parent / "observations" / (identity + ".json")
        observed.parent.mkdir()
        observed.write_bytes(b"historical observation")
        self.assertTrue(unified.initialize(self.root, self.log, "work", [], True)["changed"])

        duplicate = self.legacy_sidecar("docs/other.md", identity)
        self.assert_init_refused("old observations layout conflict")
        duplicate_bytes = duplicate.read_bytes()
        retained = duplicate.rename(duplicate.with_name("retained.json"))
        before = {path: path.read_bytes() for path in (owner, retained, observed)}
        self.assert_init_refused("old observations layout conflict")
        self.assertEqual(retained.read_bytes(), duplicate_bytes)
        self.assertEqual(before, {path: path.read_bytes() for path in before})

        retained.write_bytes(before[owner])
        self.assert_init_refused("old observations layout conflict")
        self.assertEqual(retained.read_bytes(), before[owner])

        observed.unlink()
        observed.parent.rmdir()
        self.assertTrue(unified.initialize(self.root, self.log, "work", [], True)["changed"])
        self.assertFalse((owner.parent / "work.json").exists())

    def test_initialize_refuses_unsafe_observation_paths(self):
        identity = "a" * 32
        owner = self.legacy_sidecar("docs/archive.md", identity)
        folder = owner.parent / "observations"
        folder.symlink_to(self.root / "missing", target_is_directory=True)
        self.assert_init_refused("old observations layout conflict")
        folder.unlink()
        folder.mkdir()
        observation = folder / (identity + ".json")
        observation.symlink_to(owner)
        self.assert_init_refused("unsafe migration path")
        self.assertTrue(observation.is_symlink())
        observation.unlink()
        os.mkfifo(observation)
        self.assert_init_refused("unsafe migration path")
        self.assertTrue(observation.is_fifo())

    def test_initialize_refuses_held_legacy_or_project_writer_lock(self):
        with state.open_directory(self.root, self.root) as fd:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            for dry_run in (True, False):
                with self.assertRaisesRegex(WriterBusy, "another legacy writer"):
                    unified.initialize(self.root, self.log, "work", [], dry_run)
        self.assertFalse((self.root / "lb").exists())

        directory = self.root / "lb"
        directory.mkdir()
        with (directory / ".lock").open("wb") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            for dry_run in (True, False):
                with self.assertRaisesRegex(WriterBusy, "another run writer"):
                    unified.initialize(self.root, self.log, "work", [], dry_run)
        self.assertFalse((directory / "work.json").exists())

    def test_initialize_allows_another_section_in_the_same_sidecar(self):
        for suffix in ("md", "markdown"):
            with self.subTest(suffix=suffix):
                current = self.root / f"docs/current/work.{suffix}"
                current.parent.mkdir(parents=True, exist_ok=True)
                current.write_bytes(self.log.read_bytes())
                identity = "a" * 32
                sidecar = self.legacy_sidecar(f"docs/archive/work.{suffix}", identity)
                observed = sidecar.parent / "observations" / (identity + ".json")
                observed.parent.mkdir(exist_ok=True)
                observed.write_bytes(b"historical observation")
                before = sidecar.read_bytes()
                name = f"fresh-{suffix}"

                self.assertTrue(unified.initialize(self.root, current, name, [], True)["changed"])
                self.assertFalse((sidecar.parent / f"{name}.json").exists())
                self.assertTrue(unified.initialize(self.root, current, name, [])["changed"])
                self.assertFalse(unified.initialize(self.root, current, name, [])["changed"])
                self.assertEqual(sidecar.read_bytes(), before)
                self.assertEqual(observed.read_bytes(), b"historical observation")
                sidecar.unlink()

    def existing_run(self, *associated):
        run = self.root / "lb/fresh.json"
        run.parent.mkdir(exist_ok=True)
        identity = {
            "run_id": "b" * 32,
            "log_path": "work.md",
            "document_paths": ["work.md", *associated],
        }
        run.write_bytes(unified.encode({
            "format": unified.FORMAT, "identity": identity, "documents": {},
            "execution": {"tasks": {}, "operations": {}, "facts": []}, "monitoring": None,
        }))
        return run, identity

    def test_locate_ignores_invalid_uuids_in_unrelated_sections(self):
        run, identity = self.existing_run()
        for relative in ("docs/archive.md", "docs/archive/work.md", "docs/archive.markdown"):
            for fields in ({}, {"uuid": 7}):
                with self.subTest(relative=relative, fields=fields):
                    sidecar = state.path_for(self.root / relative, self.root)
                    before = state.encode_file({
                        relative: {"document": {"identity": {"id": "identity", **fields}}}
                    })
                    sidecar.write_bytes(before)
                    path, found = unified.locate(self.root, self.log)
                    self.assertEqual(path, run)
                    self.assertEqual(found["identity"], identity)
                    self.assertEqual(sidecar.read_bytes(), before)
                    sidecar.unlink()

    def test_locate_ignores_unencodable_unrelated_sidecar_key(self):
        run, identity = self.existing_run()
        self.assertEqual(unified.locate(self.root, self.log)[0], run)
        retained = run.with_name("retained.json")
        data = json.dumps({
            "format": state.FORMAT,
            "documents": {
                "docs/\ud800.md": {"document": {"identity": {"id": "identity", "uuid": "a" * 32}}}
            },
        }).encode("ascii")
        retained.write_bytes(data)
        path, found = unified.locate(self.root, self.log)
        self.assertEqual(path, run)
        self.assertEqual(found["identity"], identity)
        self.assertEqual(retained.read_bytes(), data)

    def test_locate_ignores_overdeep_unrelated_sidecar(self):
        run, identity = self.existing_run()
        sidecar = run.with_name("archive.md.json")
        sidecar.write_bytes(OVERDEEP_SIDECAR)
        run_before = run.read_bytes()

        path, found = unified.locate(self.root, self.log)
        self.assertEqual(path, run)
        self.assertEqual(found["identity"], identity)
        self.assertEqual(run.read_bytes(), run_before)
        self.assertEqual(sidecar.read_bytes(), OVERDEEP_SIDECAR)

    def test_locate_tolerates_unrelated_undecodable_markdown_sidecars(self):
        run, identity = self.existing_run()
        run_before = run.read_bytes()
        for suffix in ("md", "markdown"):
            sidecar = run.with_name(f"archive.{suffix}.json")
            for data in (b'{"format":', OVERDEEP_SIDECAR):
                with self.subTest(suffix=suffix, size=len(data)):
                    sidecar.write_bytes(data)
                    path, found = unified.locate(self.root, self.log)
                    self.assertEqual(path, run)
                    self.assertEqual(found["identity"], identity)
                    self.assertEqual(run.read_bytes(), run_before)
                    self.assertEqual(sidecar.read_bytes(), data)
            sidecar.unlink()

    def test_locate_recognizes_markdown_named_run_by_its_format(self):
        run, identity = self.existing_run("notes.markdown")
        run = run.rename(run.with_name("notes.markdown.json"))
        before = run.read_bytes()

        path, found = unified.locate(self.root, self.log)

        self.assertEqual(path, run)
        self.assertEqual(found["identity"], identity)
        self.assertEqual(run.read_bytes(), before)

    def test_locate_refuses_invalid_run_schema_under_markdown_name(self):
        run, _ = self.existing_run()
        invalid = run.with_name("other.markdown.json")
        invalid.write_bytes(unified.encode({"format": unified.FORMAT}))
        with self.assertRaisesRegex(LbError, "invalid unified state other.markdown.json"):
            unified.locate(self.root, self.log)

    def test_locate_keeps_undecodable_markdown_blocking_legacy_recovery_fallback(self):
        sidecar = self.root / "lb/archive.markdown.json"
        sidecar.parent.mkdir()
        sidecar.write_bytes(b'{"format":')
        with self.assertRaisesRegex(LbError, "invalid state archive.markdown.json"):
            unified.locate(self.root, self.log, recovering_dependencies=True)

    def test_locate_finds_pending_dependency_recovery_with_unrelated_bad_sidecar(self):
        run, identity = self.existing_run()
        run.with_name("archive.markdown.json").write_bytes(b'{"format":')
        journal = dependency_transaction.journal_for(run)
        journal.write_bytes(b"pending dependency transaction")
        with self.assertRaisesRegex(LbError, "unfinished dependency transaction"):
            unified.locate(self.root, self.log)

        path, found = unified.locate(self.root, self.log, recovering_dependencies=True)

        self.assertEqual(path, run)
        self.assertEqual(found["identity"], identity)
        self.assertEqual(journal.read_bytes(), b"pending dependency transaction")

    def test_locate_refuses_unsafe_markdown_sidecar_files(self):
        run, _ = self.existing_run()
        sidecar = run.with_name("archive.markdown.json")
        sidecar.symlink_to(run)
        with self.assertRaisesRegex(LbError, "unsafe state symlink"):
            unified.locate(self.root, self.log)

        sidecar.unlink()
        os.mkfifo(sidecar)
        with self.assertRaisesRegex(LbError, "invalid state archive.markdown.json"):
            unified.locate(self.root, self.log)

    def test_locate_refuses_overdeep_sidecar_at_bound_document_path(self):
        run, _ = self.existing_run()
        sidecar = run.with_name("work.md.json")
        sidecar.write_bytes(OVERDEEP_SIDECAR)
        run_before = run.read_bytes()
        with self.assertRaisesRegex(LbError, "JSON nesting is too deep") as refusal:
            unified.locate(self.root, self.log)
        self.assertEqual(refusal.exception.code, 4)
        self.assertEqual(run.read_bytes(), run_before)
        self.assertEqual(sidecar.read_bytes(), OVERDEEP_SIDECAR)

    def test_locate_refuses_undecodable_sidecar_for_bound_markdown_document(self):
        run, _ = self.existing_run("notes.markdown")
        run_before = run.read_bytes()
        sidecar = run.with_name("notes.markdown.json")
        for data in (b'{"format":', OVERDEEP_SIDECAR):
            with self.subTest(size=len(data)):
                sidecar.write_bytes(data)
                with self.assertRaisesRegex(LbError, "invalid state file .*notes.markdown.json"):
                    unified.locate(self.root, self.log)
                self.assertEqual(run.read_bytes(), run_before)
                self.assertEqual(sidecar.read_bytes(), data)

    def test_initialize_refuses_overdeep_sidecar_in_observation_inventory(self):
        folder = self.root / "lb/observations"
        folder.mkdir(parents=True)
        observed = folder / ("a" * 32 + ".json")
        observed.write_bytes(b"historical observation")
        for suffix in ("md", "markdown"):
            with self.subTest(suffix=suffix):
                sidecar = folder.parent / f"archive.{suffix}.json"
                sidecar.write_bytes(OVERDEEP_SIDECAR)
                self.assert_init_refused("JSON nesting is too deep")
                self.assertEqual(sidecar.read_bytes(), OVERDEEP_SIDECAR)
                sidecar.unlink()
        self.assertEqual(observed.read_bytes(), b"historical observation")

    def test_initialize_refuses_unencodable_owner_of_observed_uuid(self):
        folder = self.root / "lb/observations"
        folder.mkdir(parents=True)
        identity = "a" * 32
        observed = folder / (identity + ".json")
        observed.write_bytes(b"historical observation")
        retained = folder.parent / "retained.json"
        data = json.dumps({
            "format": state.FORMAT,
            "documents": {
                "docs/\ud800.md": {
                    "document": {"identity": {"id": "identity", "uuid": identity}}
                }
            },
        }).encode("ascii")
        retained.write_bytes(data)
        self.assert_init_refused("unsafe legacy document section path")
        self.assertEqual(retained.read_bytes(), data)
        self.assertEqual(observed.read_bytes(), b"historical observation")

    def test_locate_does_not_require_unique_owners_for_unrelated_observations(self):
        run, identity = self.existing_run()
        owner = self.legacy_sidecar("docs/archive.md", "a" * 32)
        retained = run.with_name("retained.json")
        retained.write_bytes(owner.read_bytes())
        unrelated = run.with_name("unfamiliar.md.json")
        unrelated.write_text(json.dumps({"format": "example-export", "documents": {}}))
        observed = run.parent / "observations" / ("a" * 32 + ".json")
        observed.parent.mkdir()
        observed.write_bytes(b"historical observation")
        before = {path: path.read_bytes() for path in (owner, retained, unrelated, observed)}
        path, found = unified.locate(self.root, self.log)
        self.assertEqual(path, run)
        self.assertEqual(found["identity"], identity)
        self.assertEqual(before, {path: path.read_bytes() for path in before})

    def test_locate_refuses_misplaced_associated_section_with_no_uuid(self):
        self.existing_run("notes.markdown")
        sidecar = self.root / "lb/misplaced.md.json"
        sidecar.write_bytes(state.encode_file({"notes.markdown": {}}))
        with self.assertRaisesRegex(LbError, "old document layout conflicts"):
            unified.locate(self.root, self.log)

    def test_locate_refuses_renamed_sidecar_for_any_bound_document(self):
        run, _ = self.existing_run("notes.markdown")
        retained = run.with_name("retained.json")
        for relative in ("work.md", "notes.markdown"):
            with self.subTest(relative=relative):
                before = state.encode_file({
                    relative: {"document": {"identity": {"id": "identity", "uuid": "a" * 32}}}
                })
                retained.write_bytes(before)
                with self.assertRaisesRegex(LbError, "old document layout conflicts"):
                    unified.locate(self.root, self.log)
                self.assertEqual(retained.read_bytes(), before)

    def existing_migrated_run(self):
        for relative in ("notes.md", "reference.md"):
            (self.root / relative).write_text("# Example\n")
        main = self.legacy_sidecar("work.md", "b" * 32)
        reference = self.legacy_sidecar("reference.md", "c" * 32)
        sources = {path: path.read_bytes() for path in (main, reference)}
        run, identity = self.existing_run("notes.md", "reference.md")
        manifest = {
            "plan_token": "a" * 64,
            "backup_sha256": "b" * 64,
            "sources": {
                path.relative_to(self.root).as_posix(): hashlib.sha256(data).hexdigest()
                for path, data in sources.items()
            },
            "document_uuids": {"work.md": "b" * 32, "reference.md": "c" * 32},
            "execution_name": None,
            "send_task_mapping": {},
        }
        envelope = json.loads(run.read_bytes())
        run.write_bytes(unified.encode(envelope | {"legacy_migration": manifest}))
        run.with_suffix(".migration-done").write_bytes(unified.encode({
            "format": legacy_migration.COMMITTED,
            "document_paths": identity["document_paths"],
            "manifest": manifest,
            "rollback_token": "c" * 64,
        }))
        return run, sources

    def test_locate_checks_all_migrated_associations_for_legacy_conflicts(self):
        run, sources = self.existing_migrated_run()
        section = state.encode_file({
            "notes.md": {"document": {"identity": {"id": "identity", "uuid": "d" * 32}}}
        })
        for name, content in (
            ("notes.md.json", section),
            ("notes.md.transaction", b"pending transaction"),
            ("misplaced.md.json", section),
            ("retained.json", section),
        ):
            with self.subTest(name=name):
                conflict = run.with_name(name)
                conflict.write_bytes(content)
                try:
                    with self.assertRaisesRegex(LbError, "old document layout conflicts"):
                        unified.locate(self.root, self.log)
                    self.assertEqual(conflict.read_bytes(), content)
                finally:
                    conflict.unlink()
        self.assertEqual(sources, {path: path.read_bytes() for path in sources})

    def test_locate_accepts_only_unchanged_migrated_history(self):
        run, sources = self.existing_migrated_run()
        self.assertEqual(unified.locate(self.root, self.log)[0], run)
        path = run.with_name("reference.md.json")
        path.write_bytes(sources[path] + b"\n")
        with self.assertRaisesRegex(LbError, "retained legacy source changed"):
            unified.locate(self.root, self.log)

    def test_locate_ignores_non_sidecar_json_with_a_matching_document_key(self):
        run, identity = self.existing_run()
        foreign = run.with_name("export.json")
        incomplete = run.with_name("incomplete.json")
        foreign.write_text(json.dumps({"format": "example-export", "documents": {"work.md": {}}}))
        incomplete.write_text(json.dumps({"format": state.FORMAT, "documents": {}}))
        path, found = unified.locate(self.root, self.log)
        self.assertEqual(path, run)
        self.assertEqual(found["identity"], identity)

    def test_locate_allows_unrelated_legacy_execution_with_markdown_in_name(self):
        run, _ = self.existing_run()
        execution = run.with_name("archive.markdown.json")
        execution.write_text(json.dumps({
            "name": "archive.markdown", "log": "archive.md", "thinking": "notes.md",
            "advancement": "sample", "captain": "example", "facts": [], "operations": [],
        }))
        self.assertEqual(unified.locate(self.root, self.log)[0], run)

    def test_initialize_requires_valid_uuid_to_admit_observations(self):
        sidecar = self.legacy_sidecar("docs/archive.md", "broken")
        observed = sidecar.parent / "observations" / ("a" * 32 + ".json")
        observed.parent.mkdir()
        observed.write_bytes(b"historical observation")
        self.assert_init_refused("missing or invalid document identity")

    def test_initialize_refuses_unknown_sections_and_shared_sidecar_transactions(self):
        sidecar = self.legacy_sidecar("docs/archive/work.md", "a" * 32)
        journal = state.journal_for(self.log, self.root)
        journal.write_bytes(b"pending transaction")
        self.assert_init_refused("old layout conflict")
        self.assertEqual(journal.read_bytes(), b"pending transaction")
        journal.unlink()

        bad_owner = b'{"format":"lb-document-state","documents":{}}'
        sidecar.write_bytes(bad_owner)
        self.assert_init_refused("invalid state envelope")
        self.assertEqual(sidecar.read_bytes(), bad_owner)

    def test_initialize_refuses_misfiled_selected_sections_without_observations(self):
        associated = self.root / "notes.md"
        associated.write_text("# Notes\n")
        old = self.legacy_sidecar("docs/archive.md", "a" * 32)
        observed = old.parent / "observations" / ("a" * 32 + ".json")
        observed.parent.mkdir()
        observed.write_bytes(b"historical observation")
        for relative in ("work.md", "notes.md"):
            with self.subTest(relative=relative):
                misplaced = self.legacy_sidecar(relative, "b" * 32).rename(
                    old.with_name("misplaced.md.json")
                )
                before = misplaced.read_bytes()
                for dry_run in (True, False):
                    with self.assertRaisesRegex(LbError, "old layout conflict"):
                        unified.initialize(self.root, self.log, "fresh", ["notes.md"], dry_run)
                self.assertEqual(misplaced.read_bytes(), before)
                self.assertFalse((old.parent / "fresh.json").exists())
                misplaced.unlink()

    def test_initialize_refuses_renamed_sidecar_without_observations(self):
        (self.root / "notes.markdown").write_text("# Notes\n")
        for relative in ("work.md", "notes.markdown"):
            with self.subTest(relative=relative):
                retained = self.legacy_sidecar(relative, "a" * 32).rename(
                    self.root / "lb/retained.json"
                )
                before = retained.read_bytes()
                for dry_run in (True, False):
                    with self.subTest(dry_run=dry_run):
                        with self.assertRaisesRegex(LbError, "old layout conflict"):
                            unified.initialize(
                                self.root, self.log, "fresh", ["notes.markdown"], dry_run
                            )
                self.assertEqual(retained.read_bytes(), before)
                self.assertFalse((retained.parent / ".lock").exists())
                self.assertFalse((retained.parent / "fresh.json").exists())

    def test_initialize_checks_project_lock_for_markdown_log_and_association(self):
        project = self.root / "sample"
        project.mkdir()
        (project / "mind.yaml").write_text("{}\n")
        log = project / "work.markdown"
        log.write_bytes(self.log.read_bytes())
        notes = project / "notes.markdown"
        notes.write_text("# Notes\n")

        with state.open_directory(project, project) as fd:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            for root in (project, self.root):
                for dry_run in (True, False):
                    with self.subTest(root=root, dry_run=dry_run):
                        with self.assertRaisesRegex(WriterBusy, "another legacy writer"):
                            unified.initialize(root, log, "work", [str(notes)], dry_run)
        self.assertFalse((project / "lb").exists())

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
            "run_events": {"other.md": [{"event_id": "start"}]},
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
            "identity": {"run_id": "sample", "log_path": "work.md"},
        }
        target = self.root / "lb/work.json"
        with patch("logbook_cli.unified.locate", return_value=(target, value)):
            doc = read_document(self.root, self.log)
        self.assertEqual(doc.legacy_metadata, retained)
        self.assertEqual(doc.metadata["task-archive"], retained["task-archive"])
        self.assertEqual(doc.state_path, target)
