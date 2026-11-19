import unittest
from pathlib import Path

from logbook_cli.repository import markdown_document
from logbook_cli.services.route_scope import route_scope


class RouteScopeTests(unittest.TestCase):
    def scope(self, body):
        root = Path("/example")
        return route_scope(markdown_document(body.encode(), root / "log.md", root))[
            "route_ref"
        ]

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
