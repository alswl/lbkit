"""New Task read contracts: preserve visible work without scheduling unknowns."""

from coordination_helpers import CoordinationTest

from logbook_cli.document import context, parse, workdirs
from logbook_cli.views import task_rows


class CoordinationContextTest(CoordinationTest):
    def test_pause_and_unknown_are_visible_in_parser_and_views(self):
        self.fixture("unknown.md")
        before = self.snapshot()
        doc = parse(self.log, self.root)
        self.assertEqual(
            [t.text for t in doc.stages[0].tasks], ["Undecided", "Later", "Ready"]
        )
        self.assertEqual(
            [t["text"] for t in task_rows(doc)], ["Undecided", "Later", "Ready"]
        )
        self.assertEqual(context(doc)["next_task"]["text"], "Ready")
        self.assertEqual(before, self.snapshot())

    def test_context_retains_paused_work_after_direct_markdown_edit(self):
        self.identify()
        self.log.write_text(self.log.read_text().replace("- [ ]", "- [!]"))
        before = self.snapshot()
        data = self.context()
        self.assertEqual(len(data["stages"][0]["tasks"]), 1)
        self.assertEqual(data["stages"][0]["tasks"][0]["state"], "!")
        self.assertIsNone(data["next_task"])
        self.assertEqual(before, self.snapshot())

    def test_blocker_retains_base_marker_and_is_not_scheduled(self):
        self.identify()
        self.log.write_text(self.log.read_text() + "    - Blocker: Need sample data\n")
        doc = parse(self.log, self.root)
        self.assertEqual(doc.stages[0].tasks[0].state, " ")
        self.assertEqual(self.show()["status"], "blocked")
        self.assertIsNone(context(doc)["next_task"])

    def test_resume_annotation_does_not_make_pause_schedulable(self):
        self.log.write_text(
            "# Example\n\n## Stage 01 Build\n\n"
            "- [!] Later\n    - Resume: active\n"
            "    - Blocker: Need data\n- [ ] Ready\n"
        )
        data = self.context()
        self.assertEqual(len(data["stages"][0]["tasks"]), 2)
        self.assertEqual(data["next_task"]["text"], "Ready")

    def test_malformed_machine_group_cannot_inherit_previous_machine(self):
        self.fixture("malformed-machine.md")
        groups = workdirs(parse(self.log, self.root))
        assigned = [p["path"] for g in groups for p in g["paths"]]
        self.assertIn("/workspace/example", assigned)
        self.assertNotIn("/workspace/unassigned", assigned)

    def test_ordinary_marker_control_is_unchanged_and_read_only(self):
        self.log.write_text(
            "# Example\n\n## Stage 01 Build\n\n"
            "- [ ] Ready\n- [/] Working\n- [x] Finished\n"
        )
        before = self.snapshot()
        doc = parse(self.log, self.root)
        self.assertEqual([t.state for t in doc.stages[0].tasks], [" ", "/", "x"])
        self.assertEqual(len(task_rows(doc)), 3)
        self.assertEqual(before, self.snapshot())
