"""Sidecar identity, CAS, readable Markdown and interrupted-write invariants."""

import json
import unittest
from unittest.mock import patch

import test_domain_commands as domain

from logbook_cli import records, storage
from logbook_cli.document import LbError, parse
from logbook_cli.services.common import save
from logbook_cli.state import journal_for, path_for


class DocumentStateTest(unittest.TestCase):
    setUp = domain.DomainTest.setUp
    call = domain.DomainTest.call
    token = domain.DomainTest.token
    state = domain.DomainTest.state
    json_file = domain.DomainTest.json_file
    identify = domain.DomainTest.identify
    transition = domain.DomainTest.transition
    task_view = domain.DomainTest.task_view

    def edit_state(self):
        target = path_for(self.log, self.root)
        state = json.loads(target.read_bytes())
        state["documents"]["log.md"]["note"] = {"x": {"id": "x"}}
        target.write_text(json.dumps(state))

    def test_metadata_only_result_keeps_markdown_and_invalidates_token(self):
        self.identify()
        self.transition("start")
        before = self.log.read_bytes()
        token = self.token()
        self.json_file("result.json", {"candidate": "a", "evidence": ["report"]})
        self.transition("record-result", "--input-file", "result.json")
        self.assertEqual(self.log.read_bytes(), before)
        self.assertNotEqual(token, self.token())
        self.assertIn(b"<!-- lb-task build -->", before)
        self.assertNotIn(b'"status"', before)
        state = json.loads(path_for(self.log, self.root).read_bytes())
        self.assertEqual(
            state["documents"]["log.md"]["task"]["build"]["submission"]["candidate"],
            "a",
        )
        self.call(
            "task",
            "accept",
            "log.md",
            "build",
            "--candidate",
            "a",
            "--basis",
            "review",
            "--expect-version",
            token,
            code=4,
        )

    def test_preview_touches_no_files_and_shows_sidecar(self):
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        preview = self.call(
            "task",
            "identify",
            "log.md",
            "--stage",
            "Stage 01 Build",
            "--task",
            "Build @core",
            "--task-id",
            "build",
            "--expect-version",
            self.token(),
            "--dry-run",
        )
        self.assertIn("lb/log.md.json#log.md", preview["diff"])
        self.assertIn("<!-- lb-task build -->", preview["diff"])
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.iterdir()})

    def test_external_state_edit_invalidates_cas(self):
        self.identify()
        token = self.token()
        self.edit_state()
        self.call(
            "task",
            "start",
            "log.md",
            "build",
            "--basis",
            "start",
            "--expect-version",
            token,
            code=4,
        )
        self.assertEqual(self.task_view()["status"], "pending")

    def test_delete_id_and_task_preserve_orphan_evidence(self):
        self.identify()
        before = path_for(self.log, self.root).read_bytes()
        self.log.write_text(
            self.log.read_text().replace("    <!-- lb-task build -->\n", "")
        )
        result = self.call("log", "check", "log.md", code=1)
        self.assertIn("TASK_STATE_INVALID", result.output)
        self.call("task", "show", "log.md", "build", code=4)
        self.assertEqual(path_for(self.log, self.root).read_bytes(), before)

    def test_move_within_document_and_rename_invalidate_only_criteria(self):
        self.identify()
        self.transition("start")
        self.json_file("result.json", {"candidate": "a", "evidence": ["report"]})
        self.transition("record-result", "--input-file", "result.json")
        body = self.log.read_text()
        self.log.write_text(
            body.replace("- [/] Build @core", "## Stage 02 Export\n- [/] Build @core")
        )
        self.assertEqual(self.task_view()["stage"], "Stage 02 Export")
        self.assertTrue(self.task_view()["evidence_applicable"])
        self.log.write_text(self.log.read_text().replace("Build @core", "Export @core"))
        self.assertFalse(self.task_view()["evidence_applicable"])

    def test_history_survives_reopen_and_new_submission(self):
        self.identify()
        self.transition("start")
        self.json_file("result.json", {"candidate": "a", "evidence": ["report-a"]})
        self.transition("record-result", "--input-file", "result.json")
        self.transition("accept", "--candidate", "a")
        self.transition("reopen")
        self.json_file("result.json", {"candidate": "b", "evidence": ["report-b"]})
        self.transition("record-result", "--input-file", "result.json")
        history = self.task_view()["history"]
        self.assertTrue(
            any(r.get("acceptance", {}).get("candidate") == "a" for r in history)
        )
        self.assertEqual(self.task_view()["submission"]["candidate"], "b")

    def test_interrupted_pair_refuses_reads_and_recovers(self):
        token = self.token()
        replace = storage._replace
        calls = []

        def interrupt(path, data, expected):
            calls.append(path)
            if len(calls) == 2:
                raise OSError("simulated interruption")
            replace(path, data, expected)

        with patch.object(storage, "_replace", side_effect=interrupt):
            self.call(
                "task",
                "identify",
                "log.md",
                "--stage",
                "Stage 01 Build",
                "--task",
                "Build @core",
                "--task-id",
                "build",
                "--expect-version",
                token,
                code=4,
            )
        self.assertTrue(journal_for(self.log, self.root).exists())
        self.call("log", "context", "log.md", code=4)
        preview = self.call("log", "recover", "log.md", "--dry-run")
        self.assertFalse(preview["recovered"])
        self.call("log", "recover", "log.md", "--expect-version", "stale", code=4)
        self.call(
            "log", "recover", "log.md", "--expect-version", preview["version_token"]
        )
        self.assertFalse(journal_for(self.log, self.root).exists())
        self.assertEqual(self.task_view()["id"], "build")

    def test_recovery_never_overwrites_later_human_edit(self):
        doc = parse(self.log, self.root)
        records.put(
            doc,
            "lifecycle",
            {
                "value": "active",
                "at": "2026-01-01T00:00:00Z",
                "basis": "decision",
                "previous": "unknown",
            },
        )
        with patch.object(storage, "_replace", side_effect=OSError("interruption")):
            with self.assertRaises(OSError):
                storage.write_bytes(doc, doc.data + b"\n", False)
        self.log.write_bytes(self.log.read_bytes() + b"Human edit\n")
        before = self.log.read_bytes()
        self.call("log", "recover", "log.md", "--dry-run", code=4)
        self.assertEqual(before, self.log.read_bytes())
        self.assertTrue(journal_for(self.log, self.root).exists())

    def test_stale_snapshot_cannot_write_and_symlink_state_refused(self):
        self.identify()
        doc = parse(self.log, self.root)
        target = path_for(self.log, self.root)
        self.edit_state()
        with self.assertRaises(LbError):
            save(doc, doc.text, False)
        target.unlink()
        target.symlink_to(self.thinking)
        self.call("log", "context", "log.md", code=4)

    def test_duplicate_json_keys_and_merge_markers_refused(self):
        target = path_for(self.log, self.root)
        target.parent.mkdir()
        for content in [
            '{"format":"lb-document-state","documents":{},"documents":{}}',
            "<<<<<<< ours\n{}\n=======\n{}\n>>>>>>> theirs",
        ]:
            target.write_text(content)
            self.call("log", "context", "log.md", code=4)

    def test_legacy_json_is_rejected_without_changes(self):
        self.log.write_text(self.log.read_text() + '\n<!-- lb-task {"id":"old"} -->\n')
        before = self.log.read_bytes()
        self.call("log", "context", "log.md", code=4)
        self.assertEqual(before, self.log.read_bytes())
        self.assertFalse(path_for(self.log, self.root).exists())

    def test_last_moment_editor_change_is_not_overwritten(self):
        before = self.log.read_bytes()
        real_fsync = storage.os.fsync

        def editor_write(fd):
            self.log.write_bytes(before + b"human change\n")
            real_fsync(fd)

        with patch.object(storage.os, "fsync", side_effect=editor_write):
            with self.assertRaises(LbError):
                storage._replace(self.log, b"replacement", before)
        self.assertEqual(self.log.read_bytes(), before + b"human change\n")

    def test_mind_documents_share_one_lb_file_with_independent_tokens(self):
        project = self.root / "projects" / "demo"
        for folder in ("docs", "thinking"):
            (project / folder).mkdir(parents=True)
            (project / folder / "delivery.md").write_text("# Delivery\n")
        (project / "mind.yaml").write_text('schema: "1"\n')
        log = parse(project / "docs" / "delivery.md", self.root)
        thinking = parse(project / "thinking" / "delivery.md", self.root)
        records.put(thinking, "retro", {"id": "r1"})
        save(thinking, thinking.text, False)
        target = project / "lb" / "delivery.md.json"
        self.assertEqual(path_for(log.path, self.root), target)
        self.assertEqual(
            list(json.loads(target.read_bytes())["documents"]), ["thinking/delivery.md"]
        )
        # The Logbook snapshot predates the Thinking write but its section is intact.
        records.put(log, "retro", {"id": "r2"})
        save(log, log.text, False)
        self.assertEqual(
            sorted(json.loads(target.read_bytes())["documents"]),
            ["docs/delivery.md", "thinking/delivery.md"],
        )
        self.assertEqual(sorted(p.name for p in (project / "lb").iterdir()), ["delivery.md.json"])
