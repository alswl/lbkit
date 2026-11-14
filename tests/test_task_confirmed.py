"""Explicit human confirmation lifts ownership protection, not write guards."""

from coordination_helpers import CoordinationTest


class ConfirmedHumanTaskTest(CoordinationTest):
    def setUp(self):
        super().setUp()
        self.text = "Human review: approve result 👱"
        self.log.write_text(
            "# Example\n\n## Stage 01 Build\n\n- [ ] " + self.text + "\n"
        )

    def update(self, *extra, code=0, token=None):
        return self.cli(
            "task",
            "update",
            "log.md",
            "--stage",
            "Stage 01 Build",
            "--task",
            self.text,
            "--status",
            "x",
            "--expect-version",
            token or self.token(),
            *extra,
            code=code,
        )

    def test_unconfirmed_completion_refuses_and_confirmed_completion_writes(self):
        before = self.snapshot()
        self.update(code=4)
        self.assertEqual(self.snapshot(), before)
        self.update("--confirmed")
        self.assertIn("- [x] " + self.text, self.log.read_text())

    def test_confirmation_preserves_dry_run_and_stale_token_guards(self):
        token = self.token()
        before = self.snapshot()
        self.update("--confirmed", "--dry-run")
        self.assertEqual(self.snapshot(), before)
        self.log.write_text(self.log.read_text() + "\nHuman note.\n")
        before = self.snapshot()
        self.update("--confirmed", token=token, code=4)
        self.assertEqual(self.snapshot(), before)

    def test_identified_task_uses_confirmed_semantic_actions(self):
        self.identify(self.text)
        self.action("complete", code=4)
        self.action("complete", "T1", "--confirmed")
        self.assertEqual(self.show()["status"], "done")
        self.action("pause", "T1", "--confirmed", code=4)
        self.action("reopen", "T1", "--confirmed")
        self.assertEqual(self.show()["status"], "active")
        self.action("cancel", "T1", "--confirmed")
        self.assertEqual(self.show()["status"], "cancelled")

    def detail(self, action, *extra, code=0, token=None):
        return self.cli(
            "task",
            action,
            "log.md",
            "--stage",
            "Stage 01 Build",
            "--task",
            self.text,
            "--expect-version",
            token or self.token(),
            *extra,
            code=code,
        )

    def test_confirmed_human_annotations_and_artifact(self):
        self.detail(
            "note", "--kind", "Acceptance", "--text", "Human-approved criterion", code=4
        )
        self.detail(
            "note",
            "--kind",
            "Acceptance",
            "--text",
            "Human-approved criterion",
            "--confirmed",
        )
        item = self.context()["stages"][0]["tasks"][0]
        annotation = next(a for a in item["annotations"] if a["kind"] == "acceptance")
        self.detail(
            "note",
            "--kind",
            "Acceptance",
            "--replace-line",
            str(annotation["line"]),
            "--text",
            "Updated human criterion",
            "--confirmed",
        )
        self.detail("artifact", "--artifact", "Human-approved result", code=4)
        self.detail("artifact", "--artifact", "Human-approved result", "--confirmed")
        text = self.log.read_text()
        self.assertIn("Updated human criterion", text)
        self.assertIn("Human-approved result", text)
        self.assertIn("- [ ] " + self.text, text)

    def test_confirmed_annotation_preserves_line_kind_and_completed_checks(self):
        self.detail("note", "--kind", "Status", "--text", "Existing status")
        line = self.context()["stages"][0]["tasks"][0]["annotations"][0]["line"]
        before = self.snapshot()
        self.detail(
            "note",
            "--kind",
            "Source",
            "--replace-line",
            str(line),
            "--text",
            "Wrong kind",
            "--confirmed",
            code=4,
        )
        self.assertEqual(self.snapshot(), before)
        self.update("--confirmed")
        self.detail(
            "note",
            "--kind",
            "Acceptance",
            "--text",
            "Changed after completion",
            "--confirmed",
            code=4,
        )

    def test_confirmed_rewrite_preserves_identity_ownership_and_repository(self):
        self.identify(self.text)
        new = "Human review: revised criterion 👱"
        self.detail(
            "rewrite", "--text", new, "--decision", "Human requested rewrite", code=4
        )
        self.detail(
            "rewrite",
            "--text",
            new,
            "--decision",
            "Human requested rewrite",
            "--confirmed",
        )
        self.assertEqual(self.show()["id"], "T1")
        self.assertTrue(self.show()["human"])
        self.text = new
        for forbidden in ("Development: take over review", new + " @other-repo"):
            self.detail(
                "rewrite",
                "--text",
                forbidden,
                "--decision",
                "Human instruction",
                "--confirmed",
                code=4,
            )
        self.action("complete", "T1", "--confirmed")
        self.detail(
            "rewrite",
            "--text",
            new,
            "--decision",
            "Human instruction",
            "--confirmed",
            code=4,
        )

    def test_confirmed_detail_preserves_preview_cas_and_preflight(self):
        token = self.token()
        before = self.snapshot()
        self.detail(
            "note",
            "--kind",
            "Source",
            "--text",
            "Human supplied source",
            "--confirmed",
            "--dry-run",
        )
        self.assertEqual(self.snapshot(), before)
        self.log.write_text(self.log.read_text() + "\nOther human edit.\n")
        self.detail(
            "note",
            "--kind",
            "Source",
            "--text",
            "Human supplied source",
            "--confirmed",
            token=token,
            code=4,
        )
        self.log.write_text(self.log.read_text() + "\n- [ ] 🔮 Discuss scope\n")
        before = self.snapshot()
        self.detail(
            "rewrite",
            "--text",
            self.text,
            "--decision",
            "Human instruction",
            "--confirmed",
            code=4,
        )
        self.assertEqual(self.snapshot(), before)
