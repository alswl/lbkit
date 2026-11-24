import unittest
from pathlib import Path

from logbook_cli.repository import markdown_document
from logbook_cli.services.route_scope import route_scope

TWO_STAGE_ROUTE = """# Work

Goal: Deliver the example in order.
Working directories:
- `fixture-host`
  - `/example/work`

## Stage 01 Prepare

Goal: Prepare the example input.

- [ ] Prepare input
    <!-- lb-task a -->

## Stage 02 Verify

Goal: Verify the example output.

- [ ] Verify output
    <!-- lb-task b -->
    - Depends: a
"""


class RouteScopeTests(unittest.TestCase):
    def reviewed(self, body):
        root = Path("/example")
        return route_scope(markdown_document(body.encode(), root / "log.md", root))

    def scope(self, body):
        return self.reviewed(body)["route_ref"]

    def test_directory_line_positions_stay_visible_without_changing_scope(self):
        before = self.reviewed(TWO_STAGE_ROUTE)
        after = self.reviewed(
            TWO_STAGE_ROUTE.replace("Working directories:", "\nWorking directories:")
        )
        old_group = before["directories"][0]
        new_group = after["directories"][0]
        self.assertEqual(new_group["line"], old_group["line"] + 1)
        self.assertEqual(
            new_group["paths"][0]["line"], old_group["paths"][0]["line"] + 1
        )
        with self.subTest(scope="route"):
            self.assertEqual(before["route_ref"], after["route_ref"])
        with self.subTest(scope="task a"):
            self.assertEqual(before["task_scopes"]["a"], after["task_scopes"]["a"])

    def test_stage_goal_changes_route_and_relevant_task_scope(self):
        before = self.reviewed(TWO_STAGE_ROUTE)
        first_stage_changed = self.reviewed(
            TWO_STAGE_ROUTE.replace("Prepare the example input.", "Prepare a checksum.")
        )
        later_stage_changed = self.reviewed(
            TWO_STAGE_ROUTE.replace(
                "Verify the example output.", "Verify the checksum."
            )
        )
        with self.subTest(scope="route after first-stage change"):
            self.assertNotEqual(before["route_ref"], first_stage_changed["route_ref"])
        with self.subTest(scope="task a after first-stage change"):
            self.assertNotEqual(
                before["task_scopes"]["a"], first_stage_changed["task_scopes"]["a"]
            )
        with self.subTest(scope="route after later-stage change"):
            self.assertNotEqual(before["route_ref"], later_stage_changed["route_ref"])
        self.assertEqual(
            before["task_scopes"]["a"], later_stage_changed["task_scopes"]["a"]
        )

    def test_stage_goal_layout_and_nested_task_goal_do_not_change_scope(self):
        before = self.reviewed(TWO_STAGE_ROUTE)
        for goal in (
            "- Goal : Prepare the example input.",
            "+ Goal: Prepare the example input.",
            "1. Goal: Prepare the example input.",
            "  Goal: Prepare the example input.",
            "   + Goal: Prepare the example input.",
        ):
            with self.subTest(goal=goal):
                after = self.reviewed(
                    TWO_STAGE_ROUTE.replace(
                        "Goal: Prepare the example input.", goal
                    ).replace(
                        "    <!-- lb-task a -->",
                        "    <!-- lb-task a -->\n    - Goal: Task note\n\n  Goal: Task prose",
                    )
                )
                self.assertEqual(before["route_ref"], after["route_ref"])
                self.assertEqual(before["task_scopes"], after["task_scopes"])
                self.assertEqual(
                    before["stages"][0]["goals"], after["stages"][0]["goals"]
                )

    def test_top_level_blocks_end_task_body_before_indented_stage_goal(self):
        for boundary in (
            "<!-- Goal: Hidden comment -->",
            "<!-- hidden\nGoal: Hidden comment\n-->",
            "```text\nGoal: Hidden code\n```",
            "~~~text\nGoal: Hidden code\n~~~",
        ):
            with self.subTest(boundary=boundary):
                route = TWO_STAGE_ROUTE.replace(
                    "Goal: Prepare the example input.\n\n", ""
                ).replace(
                    "## Stage 02 Verify",
                    f"{boundary}\n\n  Goal: Prepare the example input.\n\n"
                    "## Stage 02 Verify",
                )
                before = self.reviewed(route)
                after = self.reviewed(
                    route.replace("Prepare the example input.", "Prepare a checksum.")
                )
                self.assertEqual(
                    before["stages"][0].get("goals"),
                    ["Goal: Prepare the example input."],
                )
                self.assertNotEqual(before["route_ref"], after["route_ref"])
                self.assertNotEqual(
                    before["task_scopes"]["a"], after["task_scopes"]["a"]
                )

    def test_nested_goals_under_ordinary_lists_do_not_enter_stage_scope(self):
        for parent, child in (
            ("- Stage notes", "  - Goal: Original."),
            ("1. Stage notes", "   - Goal: Original."),
            (" - Stage notes", "   Goal: Original."),
        ):
            with self.subTest(parent=parent, child=child):
                route = TWO_STAGE_ROUTE.replace(
                    "Goal: Prepare the example input.",
                    f"{parent}\n\n{child}\n\nGoal: Prepare the example input.",
                )
                before = self.reviewed(route)
                after = self.reviewed(route.replace("Original.", "Edited."))
                self.assertEqual(
                    before["stages"][0]["goals"], ["Goal: Prepare the example input."]
                )
                self.assertEqual(before["route_ref"], after["route_ref"])
                self.assertEqual(before["task_scopes"], after["task_scopes"])

    def test_thematic_break_does_not_make_following_stage_goal_a_list_child(self):
        for line in (
            "- - -",
            "* * *",
            "_ _ _",
            "---",
            "   -  - -  \t",
            "-\t-\t-",
            "****",
        ):
            with self.subTest(line=line):
                route = TWO_STAGE_ROUTE.replace(
                    "Goal: Prepare the example input.",
                    f"{line}\n\n   Goal: Prepare the example input.",
                )
                before = self.reviewed(route)
                after = self.reviewed(
                    route.replace("Prepare the example input.", "Prepare a checksum.")
                )
                self.assertEqual(
                    before["stages"][0].get("goals"),
                    ["Goal: Prepare the example input."],
                )
                self.assertNotEqual(before["route_ref"], after["route_ref"])
                self.assertNotEqual(
                    before["task_scopes"]["a"], after["task_scopes"]["a"]
                )

    def test_short_mixed_and_textual_list_items_still_own_indented_goals(self):
        for line in (
            "- -",
            "* *",
            "- * -",
            "- * * *",
            "- - - notes",
            "- - - <!-- note -->",
            "* Stage notes",
        ):
            with self.subTest(line=line):
                route = TWO_STAGE_ROUTE.replace(
                    "Goal: Prepare the example input.", f"{line}\n\n  Goal: Task note."
                )
                before = self.reviewed(route)
                after = self.reviewed(route.replace("Task note.", "Edited note."))
                self.assertEqual(before["stages"][0].get("goals", []), [])
                self.assertEqual(before["route_ref"], after["route_ref"])
                self.assertEqual(before["task_scopes"], after["task_scopes"])

    def test_list_goal_padding_distinguishes_prose_from_indented_code(self):
        canonical = self.reviewed(TWO_STAGE_ROUTE)
        goal = "Goal: Prepare the example input."
        for prefix in ("- ", "-    ", "*   ", "  12.    ", "-\t", "1.\t  "):
            with self.subTest(prefix=prefix):
                route = TWO_STAGE_ROUTE.replace(goal, prefix + goal)
                before = self.reviewed(route)
                after = self.reviewed(
                    route.replace("Prepare the example input.", "Changed.")
                )
                self.assertEqual(before["stages"][0]["goals"], [goal])
                self.assertEqual(before["route_ref"], canonical["route_ref"])
                self.assertEqual(before["task_scopes"], canonical["task_scopes"])
                self.assertNotEqual(before["route_ref"], after["route_ref"])
                self.assertNotEqual(
                    before["task_scopes"]["a"], after["task_scopes"]["a"]
                )

        for prefix in ("-     ", "-      ", "*     ", "12.     ", "-\t  ", "1.\t   "):
            with self.subTest(prefix=prefix):
                route = TWO_STAGE_ROUTE.replace(goal, prefix + goal)
                before = self.reviewed(route)
                after = self.reviewed(
                    route.replace("Prepare the example input.", "Changed.")
                )
                self.assertEqual(before["stages"][0].get("goals", []), [])
                self.assertEqual(before["route_ref"], after["route_ref"])
                self.assertEqual(before["task_scopes"], after["task_scopes"])

    def test_directory_path_changes_route_and_task_scope(self):
        before = self.reviewed(TWO_STAGE_ROUTE)
        after = self.reviewed(
            TWO_STAGE_ROUTE.replace("/example/work", "/example/other")
        )
        self.assertNotEqual(before["route_ref"], after["route_ref"])
        self.assertNotEqual(before["task_scopes"]["a"], after["task_scopes"]["a"])

    def test_status_and_skill_annotations_do_not_change_reviewed_route(self):
        base = "# Work\n\n## Stage 1\n\n- [ ] A\n    <!-- lb-task a -->\n"
        updated = base.replace("[ ]", "[/]").replace(
            "    <!--", "    - 技能：`/demo`\n    <!--"
        )
        self.assertEqual(self.scope(base), self.scope(updated))
        self.assertNotEqual(self.scope(base), self.scope(base.replace(" A\n", " B\n")))

    def test_task_scope_keeps_unrelated_later_task_out(self):
        root = Path("/example")
        base = (
            "# Work\n\n## Stage 1\n\n- [ ] A\n    <!-- lb-task a -->\n"
            "- [ ] B\n    <!-- lb-task b -->\n"
        )
        old = route_scope(markdown_document(base.encode(), root / "log.md", root))
        new = route_scope(
            markdown_document(
                base.replace("[ ] B", "[ ] Changed B").encode(), root / "log.md", root
            )
        )
        self.assertNotEqual(old["route_ref"], new["route_ref"])
        self.assertEqual(old["task_scopes"]["a"], new["task_scopes"]["a"])
        self.assertNotEqual(old["task_scopes"]["b"], new["task_scopes"]["b"])

    def test_order_responsibility_dependencies_and_acceptance_are_reviewed(self):
        from logbook_cli.document import LbError

        base = (
            "# Work\n\n## Stage 1\n\n- [ ] A\n    <!-- lb-task a -->\n"
            "- [ ] B\n    <!-- lb-task b -->\n"
        )
        reference = self.scope(base)
        for changed in (
            base.replace("Stage 1", "Stage 2"),
            base.replace("[ ] B", "[ ] B 👱"),
            base.replace(
                "    <!-- lb-task b",
                "    - Acceptance: Verified output\n    <!-- lb-task b",
            ),
            base.replace("    <!-- lb-task b", "    - Depends: a\n    <!-- lb-task b"),
        ):
            with self.subTest(changed=changed):
                self.assertNotEqual(self.scope(changed), reference)
        for missing_or_duplicate in (
            base.replace("    <!-- lb-task a -->\n", ""),
            base.replace("lb-task b", "lb-task a"),
        ):
            with self.assertRaises(LbError):
                self.scope(missing_or_duplicate)
