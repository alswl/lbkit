"""New lifecycle contracts through real bin/lb; missing routes must fail, not skip."""

import json

from coordination_helpers import CoordinationTest


class CoordinationTasksE2ETest(CoordinationTest):
    def test_simple_complete_needs_neither_start_run_nor_result(self):
        self.identify()
        self.action("complete")
        self.assertEqual(self.show()["status"], "done")
        self.assertIn("- [x] Correct typo", self.log.read_text())
        self.assertNotIn("submission", self.show())
        self.assertNotIn("run-event", json.dumps(self.show()))

    def test_pause_resume_retains_underlying_state(self):
        self.identify()
        self.action("pause")
        self.assertIn("- [!]", self.log.read_text())
        self.assertEqual(self.show()["status"], "pause")
        self.action("resume")
        self.assertEqual(self.show()["status"], "pending")
        self.assertNotIn("Resume:", self.log.read_text())

    def test_block_pause_resume_unblock(self):
        self.identify()
        self.action("start")
        self.action("block", "T1", "--reason", "Need sample data")
        self.assertEqual(self.show()["status"], "blocked")
        self.action("pause")
        self.action("resume")
        self.assertEqual(self.show()["status"], "blocked")
        self.action("unblock")
        self.assertEqual(self.show()["status"], "active")

    def test_resume_without_prior_state_requires_explicit_choice(self):
        self.identify()
        self.log.write_text(self.log.read_text().replace("- [ ]", "- [!]"))
        before = self.snapshot()
        self.action("resume", code=4)
        self.assertEqual(before, self.snapshot())
        self.action("resume", "T1", "--to", "pending")
        self.assertEqual(self.show()["status"], "pending")

    def test_complete_human_gate_refuses_without_writes(self):
        self.log.write_text(self.log.read_text().replace("Correct typo", "Review 👱"))
        self.identify("Review 👱")
        before = self.snapshot()
        self.action("complete", code=4)
        self.assertEqual(before, self.snapshot())

    def test_stale_complete_refuses_without_partial_write(self):
        self.identify()
        token = self.token()
        self.log.write_text(self.log.read_text() + "\nHuman note\n")
        before = self.snapshot()
        self.action("complete", token=token, code=4)
        self.assertEqual(before, self.snapshot())

    def test_complete_dry_run_is_read_only(self):
        self.identify()
        before = self.snapshot()
        self.action("complete", "T1", "--dry-run")
        self.assertEqual(before, self.snapshot())

    def test_cancelled_dependency_does_not_allow_start(self):
        self.identify()
        self.log.write_text(self.log.read_text() + "- [ ] Verify\n    - Depends: T1\n")
        self.identify("Verify", "T2")
        self.action("cancel")
        before = self.snapshot()
        self.action("start", "T2", code=4)
        self.assertEqual(before, self.snapshot())

    def test_split_removes_old_current_item_and_preserves_history(self):
        # Existing split invocation remains a compatibility surface for unbound work.
        self.log.write_text(
            self.log.read_text().replace("- [ ]", "- [/]")
            + "    - Artifact: example historical report\n"
        )
        self.cli(
            "task",
            "split",
            "log.md",
            "--stage",
            "Stage 01 Build",
            "--task",
            "Correct typo",
            "--into",
            "Correct heading",
            "--into",
            "Correct paragraph",
            "--decision",
            "Approved replacement",
            "--expect-version",
            self.token(),
        )
        tasks = self.context()["stages"][0]["tasks"]
        self.assertEqual(
            [t["text"] for t in tasks], ["Correct heading", "Correct paragraph"]
        )
        history = "\n".join(
            v.decode() for k, v in self.snapshot().items() if k != "log.md"
        )
        self.assertIn("Correct typo", history)
        self.assertIn("example historical report", history)

    def replacement(self, mapping, code=0):
        request = {
            "task_id": "T1",
            "replacements": [
                {"id": "T3", "text": "Correct heading"},
                {"id": "T4", "text": "Correct paragraph"},
            ],
            "reference_changes": mapping,
        }
        (self.root / "replace.json").write_text(json.dumps(request))
        return self.cli(
            "task",
            "split",
            "log.md",
            "--input-file",
            "replace.json",
            "--decision",
            "Approved replacement",
            "--expect-version",
            self.token(),
            code=code,
        )

    def linked_tasks(self):
        self.identify()
        self.log.write_text(self.log.read_text() + "- [ ] Verify\n    - Depends: T1\n")
        self.identify("Verify", "T2")

    def test_replacement_remaps_all_live_dependencies(self):
        self.linked_tasks()
        self.replacement({"T2": ["T3", "T4"]})
        rows = self.context()["stages"][0]["tasks"]
        self.assertEqual({t["id"] for t in rows}, {"T2", "T3", "T4"})
        self.assertEqual(set(self.show("T2")["depends_on"]), {"T3", "T4"})

    def test_replacement_missing_reference_map_refuses_atomically(self):
        self.linked_tasks()
        # Request is input, not a product side effect.
        (self.root / "replace.json").write_text(
            json.dumps(
                {
                    "task_id": "T1",
                    "replacements": [
                        {"id": "T3", "text": "Heading"},
                        {"id": "T4", "text": "Paragraph"},
                    ],
                    "reference_changes": {},
                }
            )
        )
        before = self.snapshot()
        self.cli(
            "task",
            "split",
            "log.md",
            "--input-file",
            "replace.json",
            "--decision",
            "Approved replacement",
            "--expect-version",
            self.token(),
            code=4,
        )
        self.assertEqual(before, self.snapshot())

    def test_replacement_refuses_unidentified_live_dependent(self):
        self.identify()
        self.log.write_text(self.log.read_text() + "- [ ] Verify\n    - Depends: T1\n")
        (self.root / "replace.json").write_text(
            json.dumps(
                {
                    "task_id": "T1",
                    "replacements": [
                        {"id": "T3", "text": "Correct heading"},
                        {"id": "T4", "text": "Correct paragraph"},
                    ],
                    "reference_changes": {},
                }
            )
        )
        before = self.snapshot()
        result = self.cli(
            "task",
            "split",
            "log.md",
            "--input-file",
            "replace.json",
            "--decision",
            "Approved replacement",
            "--expect-version",
            self.token(),
            code=4,
        )
        self.assertIn("identify", result.stderr)
        self.assertEqual(before, self.snapshot())
        self.identify("Verify", "T2")
        self.replacement({"T2": ["T3", "T4"]})
        self.assertEqual(set(self.show("T2")["depends_on"]), {"T3", "T4"})

    def test_unidentified_split_preserves_prerequisites(self):
        self.identify()
        self.log.write_text(self.log.read_text() + "- [ ] Verify\n    - Depends: T1\n")
        self.cli(
            "task",
            "split",
            "log.md",
            "--stage",
            "Stage 01 Build",
            "--task",
            "Verify",
            "--into",
            "Verify heading",
            "--into",
            "Verify paragraph",
            "--decision",
            "Approved replacement",
            "--expect-version",
            self.token(),
        )
        rows = self.context()["stages"][0]["tasks"]
        replacements = [row["id"] for row in rows if row["text"].startswith("Verify")]
        self.assertEqual(len(replacements), 2)
        for task_id in replacements:
            self.assertEqual(self.show(task_id)["depends_on"], ["T1"])
            before = self.snapshot()
            self.action("start", task_id, code=4)
            self.assertEqual(before, self.snapshot())
        self.action("complete", "T1")
        for task_id in replacements:
            self.action("start", task_id)

    def test_archived_identity_cannot_be_assigned_to_new_work(self):
        self.identify()
        self.replacement({})
        self.log.write_text(self.log.read_text() + "- [ ] Different work\n")
        before = self.snapshot()
        self.cli(
            "task",
            "identify",
            "log.md",
            "--stage",
            "Stage 01 Build",
            "--task",
            "Different work",
            "--task-id",
            "T1",
            "--expect-version",
            self.token(),
            code=2,
        )
        self.assertEqual(before, self.snapshot())
