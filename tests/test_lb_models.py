"""Behavioral regressions from the local CR; public Markdown and CLI boundaries."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT / "src"))
from logbook_cli.document import parse
from logbook_cli.skills import extract


class ModelRegressionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.path = self.root / "projects/demo/docs/log.md"
        self.path.parent.mkdir(parents=True)

    def write(self, body):
        self.path.write_text("# Research\n\n## Stage 01 Research\n\n" + body)

    def test_named_machine_groups_keep_identity_and_legacy(self):
        from logbook_cli.document import check, context
        from logbook_cli.usage import work_dirs
        self.path.write_text("# Demo\n\n工作目录：\n\n- `machine-a`\n  - `/work/example-a`\n- local\n  - `/work/local`\n- remote `machine-b`\n  - `/work/example-b`\n\n## 🛫 Stage 01 Demo\n- [ ] Research: first\n")
        doc = parse(self.path, self.root)
        groups = context(doc)["work_directories"]
        self.assertEqual([g["group_kind"] for g in groups], ["named", "local", "remote"])
        self.assertEqual(groups[0]["machine_name"], "machine-a")
        self.assertEqual(groups[2]["machine"], "remote `machine-b`")
        self.assertFalse([x for x in check(doc) if x["code"].startswith("DIRECTORY_")])
        self.assertNotIn(Path("/work/example-a"), work_dirs(self.root, "projects"))
        self.assertIn(Path("/work/example-a"), work_dirs(self.root, "projects", "machine-a"))
        self.assertNotIn(Path("/work/example-b"), work_dirs(self.root, "projects", "machine-a"))

    def test_stage_number_letter_suffix_is_delivery(self):
        self.path.write_text(
            "# Demo\n\n## Stage 03b Insert\n\n- [ ] 开发：插入。\n\n"
            "## Stage 03bx Not\n\n- [ ] 开发：不算。\n"
        )
        stages = parse(self.path, self.root).stages
        self.assertEqual([s.is_delivery for s in stages], [True, False])

    def test_skill_chain_mixed_names_and_list_markers(self):
        for marker in ("-", "*", "+"):
            with self.subTest(marker=marker):
                self.write(
                    f"{marker} [ ] Research: summarize\n    - 技能：`mf-cli`、source-check\n"
                )
                result = extract(self.root, "projects")
                self.assertEqual(len(result), 1)
                self.assertEqual(result[0]["chain"], ["mf-cli", "source-check"])

    def test_english_fields_and_unknown_skill_syntax(self):
        self.write("- [ ] Research: summarize\n    - Skills: mf-cli, `source-check`\n")
        self.assertEqual(
            extract(self.root, "projects")[0]["chain"], ["mf-cli", "source-check"]
        )
        self.write(
            "- [ ] Research: summarize\n    - Skills: `mf-cli` ??? source-check\n"
        )
        item = extract(self.root, "projects")[0]
        self.assertEqual(item["chain"], [])
        self.assertTrue(item["diagnostics"])
        self.assertEqual(item["raw"], "`mf-cli` ??? source-check")

    def test_annotations_belong_to_one_task_and_ignore_hidden_content(self):
        self.write(
            "- [ ] Research: first\n    - Skills: mf-cli\n\n## Notes\n    - Skills: orphan\n\n```\n- [ ] Research: fake\n    - Skills: hidden\n```\n"
        )
        self.assertEqual(
            [x["chain"] for x in extract(self.root, "projects")], [["mf-cli"]]
        )

    def test_human_ownership_in_both_languages(self):
        for text in ("人工验证：结果", "Human review: result"):
            self.write("- [ ] " + text + "\n")
            doc = parse(self.path, self.root)
            self.assertTrue(doc.stages[0].tasks[0].human)

    def test_warning_summaries_and_fenced_locale_examples_stay_human(self):
        from logbook_cli.document import summary_lines

        self.path.write_text(
            "# Research\n\n```\n技能：example\n```\n\n> Status: ⚠ Needs review -- my warning\n\n## Stage 01 Research\n\n- [x] Research: done\n"
        )
        doc = parse(self.path, self.root)
        self.assertEqual(doc.locale, "en")
        self.assertFalse(summary_lines(doc)[0]["owned"])

    def test_actionless_task_is_preserved_but_not_curated(self):
        self.write("- [ ] Read the report\n    - Skills: mf-cli\n")
        doc = parse(self.path, self.root)
        self.assertIsNone(doc.stages[0].tasks[0].action)
        self.assertEqual(len(doc.stages[0].tasks[0].annotations), 1)
        self.assertEqual(extract(self.root, "projects"), [])

    def test_domain_status_has_no_presentation_values(self):
        from logbook_cli.models import StageStatus, TaskState, derive_stage_status

        self.write("- [ ] Research: first\n")
        stage = parse(self.path, self.root).stages[0]
        self.assertEqual(stage.tasks[0].status, TaskState.TODO)
        self.assertEqual(derive_stage_status(stage), StageStatus.NOT_STARTED)
        self.write("- [x] Research: first\n")
        self.assertEqual(
            derive_stage_status(parse(self.path, self.root).stages[0]),
            StageStatus.SETTLED,
        )

    def test_english_sync_and_resolution_preserve_crlf_and_human_tail(self):
        self.path.write_bytes(
            b"# Research\r\n\r\n> Status: pending Stage 01 Research -- keep my words\r\n\r\n## pending Stage 01 Research\r\n\r\n- [-] Research: cancelled\r\n"
        )

        def run(*args):
            p = subprocess.run(
                [
                    sys.executable,
                    str(KIT / "bin/lb"),
                    "--root",
                    str(self.root),
                    *args,
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(p.returncode, 0, p.stderr)
            return json.loads(p.stdout)

        rel = str(self.path.relative_to(self.root))
        token = run("context", rel, "--json")["version_token"]
        token = run(
            "task",
            "resolve",
            rel,
            "--stage",
            "Stage 01 Research",
            "--task",
            "Research: cancelled",
            "--as",
            "human-cancelled",
            "--decision",
            "human ruling",
            "--note",
            "scope removed",
            "--token",
            token,
            "--json",
        )["version_token"]
        run("sync", rel, "--token", token, "--json")
        data = self.path.read_bytes()
        self.assertIn(b"    - Resolution:", data)
        self.assertIn(b"## settled Stage 01 Research", data)
        self.assertIn(b" -- keep my words\r\n", data)
        self.assertNotIn(b"\n", data.replace(b"\r\n", b""))
        self.assertTrue(parse(self.path, self.root).stages[0].tasks[0].settled)


if __name__ == "__main__":
    unittest.main()
