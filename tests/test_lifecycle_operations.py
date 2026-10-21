"""Integration scenarios for lifecycle, delivery, metrics and reusable learning."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from click.testing import CliRunner

from logbook_cli.cli import app


class OperationsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.log = self.root / "log.md"
        self.log.write_text(
            "# Demo\n\n目标：人类目标。\n\n## 🛫 Stage 01 Build\n\n- [ ] Build @core\n- [ ] Review 👱\n"
        )
        self.thinking = self.root / "thinking.md"
        self.thinking.write_text("# Thinking\n\nHuman notes stay.\n")
        self.runner = CliRunner()

    def call(self, *args, code=0):
        result = self.runner.invoke(app, ["--root", str(self.root), *args, "--json"])
        if code == 0:
            self.assertEqual(
                result.exit_code, code, result.output + repr(result.exception)
            )
            return json.loads(result.output)
        self.assertNotEqual(result.exit_code, 0, result.output)
        return result

    def token(self, path="log.md"):
        return self.call('log', 'context', path)["version_token"]

    def state(self, value, dry=False):
        return self.call(
            'log', 'state-set',
            "log.md",
            "--lifecycle",
            value,
            "--basis",
            "Human decision reference",
            '--expect-version',
            self.token(),
            *(["--dry-run"] if dry else []),
        )

    def json_file(self, name, value):
        (self.root / name).write_text(json.dumps(value, ensure_ascii=False))
        return name

    def test_lifecycle_preview_single_line_pause_termination_and_history(self):
        original = self.log.read_bytes()
        self.state("active", True)
        self.assertEqual(self.log.read_bytes(), original)
        self.state("active")
        for _ in range(2):
            self.call('log', 'sync', "log.md", '--expect-version', self.token())
        self.assertEqual(self.log.read_text().count("> 状态："), 1)
        self.assertIn("目标：人类目标。", self.log.read_text())
        self.assertNotIn("下一项", self.log.read_text())
        self.state("paused")
        self.assertIsNone(self.call('log', 'context', "log.md")["next_task"])
        self.assertFalse(self.call('log', 'state', "log.md")["actionable"])
        before = self.log.read_bytes()
        self.call(
            "task",
            "update",
            "log.md",
            "--stage",
            "Stage 01 Build",
            "--task",
            "Build @core",
            "--status",
            "/",
            '--expect-version',
            self.token(),
            code=4,
        )
        self.assertEqual(before, self.log.read_bytes())
        self.state("terminated")
        self.assertIn("- [ ] Build @core", self.log.read_text())
        self.assertIsNone(self.call("task", "next", "log.md"))

    def test_stale_token_and_human_status_protection(self):
        old = self.token()
        self.log.write_text(self.log.read_text() + "\nHuman edit\n")
        self.call(
            'log', 'state-set',
            "log.md",
            "--lifecycle",
            "draft",
            "--basis",
            "Decision",
            '--expect-version',
            old,
            code=4,
        )
        self.log.write_text(
            self.log.read_text().replace(
                "# Demo\n", "# Demo\n\n> 状态：Human note stays\n"
            )
        )
        before = self.log.read_bytes()
        self.call(
            'log', 'state-set',
            "log.md",
            "--lifecycle",
            "draft",
            "--basis",
            "Decision",
            '--expect-version',
            self.token(),
            code=4,
        )
        self.assertEqual(before, self.log.read_bytes())

    def test_gate_allows_only_pause_or_termination(self):
        self.log.write_text(
            self.log.read_text().replace("Build @core", "🔮 Build @core")
        )
        self.call(
            'log', 'state-set',
            "log.md",
            "--lifecycle",
            "active",
            "--basis",
            "Decision",
            '--expect-version',
            self.token(),
            code=4,
        )
        self.state("paused")
        self.assertIn("🔮 Build", self.log.read_text())
        self.assertIn("⏸ 暂停", self.log.read_text())
        self.call(
            'log', 'state-set',
            "log.md",
            "--lifecycle",
            "active",
            "--basis",
            "Resume",
            '--expect-version',
            self.token(),
            code=4,
        )

    def test_completion_requires_settlement_and_detects_new_human_work(self):
        self.call(
            'log', 'state-set',
            "log.md",
            "--lifecycle",
            "completed",
            "--basis",
            "No",
            '--expect-version',
            self.token(),
            code=4,
        )
        self.log.write_text(self.log.read_text().replace("- [ ]", "- [x]"))
        self.state("completed")
        self.log.write_text(self.log.read_text() + "\n- [ ] More review 👱\n")
        state = self.call('log', 'state', "log.md")
        self.assertTrue(state["inconsistencies"])
        self.assertIn("不一致", state["summary"])
        self.assertIsNone(state["next_task"])

    def test_metadata_in_fences_is_not_lifecycle(self):
        self.log.write_text(
            self.log.read_text()
            + '\n```md\n<!-- lb-lifecycle {"value":"terminated"} -->\n```\n'
        )
        self.assertEqual(self.call('log', 'state', "log.md")["lifecycle"]["value"], "unknown")
        self.state("draft")

    def test_link_audit_separates_reference_and_rechecks_deleted_file(self):
        (self.root / "artifact.md").write_text("Candidate")
        self.log.write_text(
            self.log.read_text().replace(
                "- [ ] Review", "    - 产物：[Result](artifact.md)\n- [ ] Review"
            )
            + "\n[Background](https://example.invalid/reference)\n"
        )
        audit = self.call('log', 'links', "audit", "log.md")
        artifact = next(r for r in audit["links"] if r["required"])
        self.assertFalse(audit["delivery_ready"])
        self.call(
            'log', 'links',
            'record-check',
            "log.md",
            "--line",
            str(artifact["line"]),
            "--label",
            "Result",
            "--target",
            "artifact.md",
            "--observed-at",
            "2026-01-01T00:00:00Z",
            "--observer",
            "sailor",
            "--basis",
            "Local candidate read",
            "--result-identity",
            "candidate-a",
            '--expect-version',
            self.token(),
        )
        self.assertTrue(self.call('log', 'links', "audit", "log.md")["delivery_ready"])
        (self.root / "artifact.md").unlink()
        self.assertFalse(self.call('log', 'links', "audit", "log.md")["delivery_ready"])

    def event(self, identity, kind, at, **extra):
        return dict(
            run_id="run-a",
            event_id=identity,
            type=kind,
            scope="logbook",
            at=at,
            origin="Test observation",
            coverage="complete",
            **extra,
        )

    def record(self, item, **kwargs):
        self.json_file("event.json", item)
        return self.call(
            "log", "events",
            "record",
            "log.md",
            "--thinking",
            "thinking.md",
            '--input-file',
            "event.json",
            '--expect-version',
            self.token("thinking.md"),
            **kwargs,
        )

    def test_event_replay_correction_and_closeout_unknown(self):
        start = self.event("start", "run_start", "2026-01-01T00:00:00Z")
        self.record(start)
        before = self.thinking.read_bytes()
        replay = self.record(start)
        self.assertTrue(replay["replay"])
        self.assertEqual(before, self.thinking.read_bytes())
        self.record({**start, "origin": "Different"}, code=4)
        self.record(
            self.event(
                "first",
                "package_first_outcome",
                "2026-01-01T00:00:01Z",
                package_id="p1",
                outcome="passed",
                first_pass=True,
            )
        )
        self.record(
            self.event(
                "correction",
                "package_correction",
                "2026-01-01T00:00:02Z",
                package_id="p1",
                outcome="failed",
                first_pass=False,
                reason="Delivery missing",
                corrects="first",
            )
        )
        self.record(self.event("end", "run_end", "2026-01-01T00:00:10Z"))
        value = self.call("log", "report", "--view", "metrics", "log.md", "--thinking", "thinking.md")
        self.assertEqual(value["wall_seconds"], 10)
        self.assertEqual(value["first_pass"]["rate"], 0)
        report = self.call("log", "report", "--view", "closeout", "log.md")
        self.assertEqual(report["metrics"]["coverage"], "unknown")
        self.assertEqual(len(report["checklist"]["open"]), 2)
        self.assertIn("Human notes stay.", self.thinking.read_text())

    def test_event_write_refuses_outside_root_and_future_time(self):
        self.record(self.event("future", "run_start", "2999-01-01T00:00:00Z"), code=2)
        self.call(
            "log", "events",
            "record",
            "log.md",
            "--thinking",
            "../outside.md",
            '--input-file',
            "event.json",
            '--expect-version',
            self.token(),
            code=3,
        )

    def make_workflow(self):
        path = self.root / "workflows" / "example" / "docs" / "example.md"
        path.parent.mkdir(parents=True)
        path.write_text("""# Workflow

## 运行实例模板

槽 1 目标日 <DATE>
槽 2 工作目录
槽 3 运行裁定
标题：`# <DATE> <SUBJECT>`。

```md
## 总览

目标：Deliver <SUBJECT>.

工作目录：

<WORKDIRS>

## 🛫 Stage 01 Deliver

- [ ] Build <SUBJECT> @core
- [ ] Accept 👱
```

## 既定裁定

- Preserve review.
""")
        return path

    def test_workflow_pins_provenance_and_refuses_rewrite(self):
        self.make_workflow()
        info = self.call("workflow", "show", "example")
        inputs = self.json_file(
            "inputs.json",
            {
                "date": "2026-01-01",
                "working_directories": "- local\n  - `/approved/example`",
                "rulings": {"SUBJECT": "Report"},
            },
        )
        args = [
            "workflow",
            "render",
            "example",
            '--input-file',
            inputs,
            '--expect-version',
            info["version_token"],
        ]
        rendered = self.call(*args)
        self.assertIn("- [ ] Accept 👱", rendered["content"])
        self.assertNotIn("<WORKDIRS>", rendered["content"])
        self.call(
            "log",
            "create", "--from-workflow",
            "example",
            '--input-file',
            inputs,
            '--expect-version',
            info["version_token"],
            *(),
            "new.md",
            "--dry-run",
        )
        self.assertFalse((self.root / "new.md").exists())
        created = self.call(
            "log",
            "create", "--from-workflow",
            "example",
            '--input-file',
            inputs,
            '--expect-version',
            info["version_token"],
            *(),
            "new.md",
        )
        self.assertFalse(created["managed_workflow_complete"])
        (self.root / "linked.md").symlink_to("absent-target.md")
        self.call(
            "log",
            "create", "--from-workflow",
            "example",
            '--input-file',
            inputs,
            '--expect-version',
            info["version_token"],
            *(),
            "linked.md",
            code=4,
        )
        self.assertFalse((self.root / "absent-target.md").exists())
        self.assertFalse(self.call("workflow", "diff", "new.md")["changed"])
        self.call(
            "log",
            "create", "--from-workflow",
            "example",
            '--input-file',
            inputs,
            '--expect-version',
            info["version_token"],
            *(),
            "new.md",
            code=4,
        )
        self.assertEqual((self.root / "new.md").read_text(), rendered["content"])
        self.json_file(
            "inputs.json",
            {"date": "2026-01-01", "working_directories": "- local", "rulings": {}},
        )
        self.call(*args, code=4)

    def test_retro_keeps_dimensions_and_requires_main_branch(self):
        subprocess.run(
            ["git", "init", "-q", "--initial-branch=master", str(self.root)], check=True
        )
        (self.root / "feedback.md").write_text("# Feedback\n\nHuman prose.\n")
        item = dict(
            id="finding-a",
            summary="Review delivery",
            classification="usage",
            owner="maintainer",
            source_ids=["source-a"],
            sources=["thinking.md#observation"],
            disposition="accepted",
            implementation="implemented",
            adoption=[],
            verification=[],
        )
        self.json_file("finding.json", item)
        args = ['feedback', "record", "--ledger", "feedback.md", '--input-file', "finding.json"]
        self.call(*args, '--expect-version', self.token("feedback.md"))
        before = (self.root / "feedback.md").read_bytes()
        self.call(*args, '--expect-version', self.token("feedback.md"))
        self.assertEqual(before, (self.root / "feedback.md").read_bytes())
        value = self.call(
            'feedback', "show", "--ledger", "feedback.md", "--id", "finding-a"
        )
        self.assertEqual(value["findings"][0]["adoption"], [])
        self.json_file("finding.json", {**item, "implementation": "verified"})
        self.call(
            'feedback',
            "update",
            "--ledger",
            "feedback.md",
            '--input-file',
            "finding.json",
            '--expect-version',
            self.token("feedback.md"),
            code=4,
        )
        subprocess.run(
            ["git", "-C", str(self.root), "symbolic-ref", "HEAD", "refs/heads/feature"],
            check=True,
        )
        self.json_file("finding.json", item)
        self.call(*args, '--expect-version', self.token("feedback.md"), code=4)

    def test_link_bytes_change_invalidates_observation(self):
        (self.root / "artifact.md").write_text("Original")
        self.log.write_text(
            self.log.read_text().replace(
                "- [ ] Review", "    - 产物：[Result](artifact.md)\n- [ ] Review"
            )
        )
        row = self.call('log', 'links', "audit", "log.md")["links"][0]
        self.call(
            'log', 'links',
            'record-check',
            "log.md",
            "--line",
            str(row["line"]),
            "--label",
            "Result",
            "--target",
            "artifact.md",
            "--observed-at",
            "2026-01-01T00:00:00Z",
            "--observer",
            "sailor",
            "--basis",
            "Read candidate",
            '--expect-version',
            self.token(),
        )
        self.assertTrue(self.call('log', 'links', "audit", "log.md")["delivery_ready"])
        (self.root / "artifact.md").write_text("Different candidate")
        self.assertFalse(self.call('log', 'links', "audit", "log.md")["delivery_ready"])

    def test_template_slots_cannot_add_tasks_or_remove_human_gate(self):
        self.make_workflow()
        info = self.call("workflow", "show", "example")
        self.json_file(
            "inputs.json",
            {
                "date": "2026-01-01",
                "working_directories": "- local",
                "rulings": {"SUBJECT": "Report\n- [ ] Extra task"},
            },
        )
        self.call(
            "workflow",
            "render",
            "example",
            '--input-file',
            "inputs.json",
            '--expect-version',
            info["version_token"],
            code=4,
        )

    def test_retro_scan_uses_committed_snapshot_and_deduplicates_saved_sources(self):
        # All commits in this test are isolated disposable fixture objects.
        subprocess.run(
            ["git", "init", "-q", "--initial-branch=master", str(self.root)], check=True
        )
        feedback = self.root / "docs" / "skills-feedback.md"
        feedback.parent.mkdir()
        feedback.write_text(
            "# Feedback\n\n## Example\n\n- skill delivery needs verification.\n"
        )
        for args in (
            ["add", "docs/skills-feedback.md"],
            [
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "-qm",
                "Fixture snapshot",
            ],
        ):
            subprocess.run(["git", "-C", str(self.root), *args], check=True)
        feedback.write_text(feedback.read_text() + "\n- skill uncommitted finding.\n")
        found = self.call('feedback', "scan", "--since", "2000-01-01")
        self.assertEqual(len(found["findings"]), 1)
        self.assertTrue(found["uncommitted_excluded"])
        source = found["findings"][0]
        (self.root / "ledger.md").write_text("# Ledger\n")
        item = dict(
            id="f1",
            summary="Delivery",
            classification="usage",
            owner="maintainer",
            source_ids=[source["source_id"]],
            sources=[source["revision"] + ":" + source["path"]],
            disposition="proposed",
            implementation="not-started",
            adoption=[],
            verification=[],
        )
        self.json_file("finding.json", item)
        self.call(
            'feedback',
            "record",
            "--ledger",
            "ledger.md",
            '--input-file',
            "finding.json",
            '--expect-version',
            self.token("ledger.md"),
        )
        second = self.call(
            'feedback', "scan", "--since", "2000-01-01", "--ledger", "ledger.md"
        )
        self.assertEqual(second["findings"], [])
        self.assertIn("uncommitted finding", feedback.read_text())

    def test_event_append_refuses_unclosed_markdown(self):
        for suffix in ("```text\nunfinished\n", "<!-- unfinished\n"):
            self.thinking.write_text("# Thinking\n" + suffix)
            before = self.thinking.read_bytes()
            self.record(
                self.event("start", "run_start", "2026-01-01T00:00:00Z"), code=4
            )
            self.assertEqual(before, self.thinking.read_bytes())

    def workflow_input(self, subject="Report"):
        return self.json_file(
            "inputs.json",
            {
                "date": "2026-01-01",
                "working_directories": "- local\n  - `/approved/example`",
                "rulings": {
                    "SUBJECT": subject,
                    "RULE": "Local draft only; no publication",
                    "PREV": "no-prev",
                },
            },
        )

    def test_english_workflow_creates_instance(self):
        path = self.make_workflow()
        content = path.read_text()
        for old, new in (
            ("运行实例模板", "Run-instance template"),
            ("既定裁定", "Established rulings"),
            ("槽", "Slot"),
            ("标题：", "Title:"),
            ("目标：", "Goal:"),
            ("工作目录：", "Working directories:"),
        ):
            content = content.replace(old, new)
        path.write_text(content)
        info = self.call("workflow", "show", "example")
        self.assertTrue(info["contract_valid"])
        args = (
            "log", "create", "new.md", "--from-workflow", "example",
            "--input-file", self.workflow_input(),
            "--expect-version", info["version_token"],
        )
        preview = self.call(*args, "--dry-run")
        self.assertFalse((self.root / "new.md").exists())
        self.call(*args)
        created = (self.root / "new.md").read_text()
        self.assertEqual(created, preview["content"])
        self.assertIn("Goal:Deliver Report.", created)
        self.assertIn("- [ ] Accept 👱", created)
        self.assertEqual(path.read_text(), content)

    def test_workflow_preserves_rulings_and_frontmatter(self):
        path = self.make_workflow()
        path.write_text(
            path.read_text()
            .replace(
                "标题：", "```yaml\nworkflow: example\nprev-run: <PREV>\n```\n\n标题："
            )
            .replace(
                "<WORKDIRS>",
                "- `<MACHINE>`\n  - `<PATH>`\n\n< RULE >".replace("< RULE >", "<RULE>"),
            )
        )
        result = self.call(
            "workflow",
            "render",
            "example",
            '--input-file',
            self.workflow_input(),
            '--expect-version',
            self.token(str(path.relative_to(self.root))),
        )
        self.assertTrue(
            result["content"].startswith(
                "---\nworkflow: example\nprev-run: no-prev\n---"
            )
        )
        self.assertIn(
            "Local draft only; no publication",
            result["content"].split("<!-- lb-workflow")[0],
        )
        self.assertIn("- [ ] Accept 👱", result["content"])

    def test_workflow_create_validates_at_destination(self):
        path = self.make_workflow()
        output = self.root / "instances"
        output.mkdir()
        (path.parent / "artifact.md").write_text("template neighbor")
        args = [
            "log",
            "create", "--from-workflow",
            "example",
            '--input-file',
            self.workflow_input("[Report](artifact.md)"),
            '--expect-version',
            self.token(str(path.relative_to(self.root))),
            *(),
            "instances/new.md",
        ]
        self.call(*args, code=4)
        self.assertFalse((output / "new.md").exists())
        (output / "artifact.md").write_text("actual instance neighbor")
        self.call(*args, "--dry-run")
        self.assertFalse((output / "new.md").exists())
        self.call(*args)
        before = (output / "new.md").read_bytes()
        self.call(*args, code=4)
        self.assertEqual(before, (output / "new.md").read_bytes())

    def test_workflow_replace_is_single_file_cas(self):
        path = self.make_workflow()
        original = path.read_bytes()
        token = self.token(str(path.relative_to(self.root)))
        candidate = self.root / "candidate.md"
        candidate.write_text(
            path.read_text().replace(
                "Preserve review.", "Preserve review and explicit rulings."
            )
        )
        args = [
            "workflow",
            "update",
            "example",
            "--content-file",
            "candidate.md",
            '--expect-version',
            token,
        ]
        preview = self.call(*args, "--dry-run")
        self.assertIn("+", preview["diff"])
        self.assertEqual(original, path.read_bytes())
        self.call(*args)
        self.assertEqual(candidate.read_bytes(), path.read_bytes())
        self.call(*args, code=4)
        candidate.write_text("# Not a workflow\n")
        self.call(
            "workflow",
            "update",
            "example",
            "--content-file",
            "candidate.md",
            '--expect-version',
            self.token(str(path.relative_to(self.root))),
            code=4,
        )

    def test_workflow_create_is_only_one_file_and_never_overwrites(self):
        template = self.make_workflow()
        directory = self.root / "workflows" / "new" / "docs"
        directory.mkdir(parents=True)
        args = [
            "workflow",
            "create",
            "new",
            "--content-file",
            str(template.relative_to(self.root)),
        ]
        self.call(*args, "--dry-run")
        self.assertEqual(list(directory.iterdir()), [])
        self.call(*args)
        self.assertTrue((directory / "new.md").read_bytes().startswith(template.read_bytes()))
        self.assertEqual(self.call("workflow", "show", "new")["status"], "draft")
        self.assertFalse((directory.parent / "thinking").exists())
        self.call(*args, code=4)


if __name__ == "__main__":
    unittest.main()
