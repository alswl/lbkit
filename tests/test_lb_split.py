"""Atomic task replacement, provenance and scheduling protections."""

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CLI = Path(__file__).resolve().parents[1] / "bin/lb"
STAGE = "Stage 01 Delivery"
ORIGINAL = "开发：交付样例成果。 @sample-app"
CHILDREN = (
    "开发：交付两条可读记录。 @sample-app",
    "验证：逐项检查两条记录。 @sample-app",
)
HUMAN = "人工验证：审阅结果。 👱"
BODY = (
    "    - 技能：`/example-skill`\n"
    "    - 验收：旧条件仍需重新核验。\n"
    "    - 产物：历史结果标识 C1\n"
    "    <!-- preserve human comment -->\n"
)


class TaskSplitTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.log = self.root / "log.md"
        self.log.write_text(
            f"# Sample\n\n## 🚧 {STAGE}\n\n目标：保留人工目标。\n\n"
            f"待办：\n\n- [/] {ORIGINAL}\n{BODY}"
            f"- [ ] {HUMAN}\n    - 批注：保留。\n"
        )

    def cli(self, *args, code=0):
        result = subprocess.run(
            [sys.executable, str(CLI), "--root", str(self.root), *args, "--json"],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return json.loads(result.stdout) if code in (0, 1) else None

    def context(self):
        return self.cli('log', 'context', "log.md")

    def split(self, children=CHILDREN, task=ORIGINAL, token=None, dry_run=False, code=0):
        args = [
            "task", "split", "log.md", "--stage", STAGE, "--task", task,
            "--decision", "人工明确授权按所列顺序拆分", '--expect-version',
            token or self.context()["version_token"],
        ]
        for text in children:
            args.extend(["--into", text])
        if dry_run:
            args.append("--dry-run")
        return self.cli(*args, code=code)

    def test_split_preserves_original_evidence_and_replaces_scheduling_once(self):
        before = self.log.read_bytes()
        token = self.context()["version_token"]
        preview = self.split(token=token, dry_run=True)
        self.assertEqual(self.log.read_bytes(), before)
        self.assertEqual(preview["version_token"], token)
        self.assertIn(f"+- [-] {ORIGINAL}", preview["diff"])
        result = self.split(token=token)
        self.assertEqual(result["version_token"], self.context()["version_token"])
        self.assertNotEqual(result["version_token"], token)
        current = self.context()
        tasks = current["stages"][0]["tasks"]
        self.assertEqual([t["text"] for t in tasks], [ORIGINAL, *CHILDREN, HUMAN])
        self.assertEqual([t["state"] for t in tasks], ["-", " ", " ", " "])
        identity = hashlib.sha256(ORIGINAL.encode()).hexdigest()
        self.assertEqual(tasks[0]["resolution"]["task"], identity)
        self.assertEqual(tasks[0]["resolution"]["as"], "not-applicable")
        self.assertEqual(result["original_task"], identity)
        self.assertEqual(current["next_task"]["text"], CHILDREN[0])
        self.assertIn(BODY, self.log.read_text())
        human = before.decode().split(f"- [ ] {HUMAN}")[1]
        self.assertTrue(self.log.read_text().endswith(f"- [ ] {HUMAN}" + human))
        for child in tasks[1:3]:
            self.assertEqual([a["kind"] for a in child["annotations"]], ["source"])
            self.assertIn(identity, child["annotations"][0]["value"])
        self.assertEqual(
            [i["code"] for i in self.cli('log', 'check', "log.md", code=1)],
            ["STAGE_EMOJI"],
        )
        after = self.log.read_bytes()
        self.split(code=4)
        self.assertEqual(self.log.read_bytes(), after)

    def test_invalid_replacements_never_retire_original_or_insert_partial_tasks(self):
        before = self.log.read_bytes()
        cases = [
            ((CHILDREN[0],), 2),
            ((CHILDREN[0], CHILDREN[0]), 4),
            ((CHILDREN[0], ORIGINAL), 4),
            ((CHILDREN[0], HUMAN), 4),
            ((CHILDREN[0], "人工验证：新增。 👱"), 4),
            ((CHILDREN[0], "开发：转交。 @other"), 4),
            ((CHILDREN[0], "开发：丢失责任仓库。"), 4),
            ((CHILDREN[0], "- [ ] 开发：嵌套标记。"), 2),
            ((CHILDREN[0], "开发：换行。\n- [x] 验证：伪造。"), 2),
            ((CHILDREN[0], "  开发：空白。"), 2),
            ((CHILDREN[0], "🔮 开发：未经确认。 @sample-app"), 4),
        ]
        for children, code in cases:
            for preview in (True, False):
                with self.subTest(children=children, preview=preview):
                    self.split(children, dry_run=preview, code=code)
                    self.assertEqual(self.log.read_bytes(), before)

    def test_protected_originals_and_global_preflight_refuse_all_writes(self):
        initial = self.log.read_text()
        for text in [
            initial.replace("- [/] " + ORIGINAL, "- [x] " + ORIGINAL),
            initial.replace("- [/] " + ORIGINAL, "- [-] " + ORIGINAL),
            initial + f"- [ ] {ORIGINAL}\n",
            initial + "- [ ] 🔮 讨论：未裁定。\n",
        ]:
            with self.subTest(text=text):
                self.log.write_text(text)
                before = self.log.read_bytes()
                self.split(code=4)
                self.assertEqual(self.log.read_bytes(), before)
        self.log.write_text(initial)
        before = self.log.read_bytes()
        self.split(task=HUMAN, code=4)
        self.assertEqual(self.log.read_bytes(), before)

    def test_stale_token_does_not_overwrite_human_change(self):
        token = self.context()["version_token"]
        self.split(token=token, dry_run=True)
        self.log.write_bytes(self.log.read_bytes() + b"\n<!-- concurrent human input -->\n")
        before = self.log.read_bytes()
        self.split(token=token, code=4)
        self.assertEqual(self.log.read_bytes(), before)

    def test_repository_partition_preserves_coverage(self):
        original = ORIGINAL + " @sample-tests"
        self.log.write_text(self.log.read_text().replace(ORIGINAL, original))
        children = (CHILDREN[0], "验证：交付复核结果。 @sample-tests")
        self.split(children, task=original)
        tasks = self.context()["stages"][0]["tasks"]
        self.assertEqual([t["repositories"] for t in tasks[1:3]], [["sample-app"], ["sample-tests"]])

    def test_repository_partition_cannot_drop_an_original_owner(self):
        original = ORIGINAL + " @sample-tests"
        self.log.write_text(self.log.read_text().replace(ORIGINAL, original))
        before = self.log.read_bytes()
        self.split(task=original, code=4)
        self.assertEqual(self.log.read_bytes(), before)

    def test_unassigned_task_allows_explicit_initial_repository_choices(self):
        original = "开发：交付样例成果。"
        self.log.write_text(self.log.read_text().replace(ORIGINAL, original))
        self.split((CHILDREN[0], "验证：交付复核结果。 @sample-tests"), task=original)
        self.assertEqual(self.context()["next_task"]["repositories"], ["sample-app"])

    def test_english_crlf_and_missing_final_newline(self):
        original = "Develop: deliver sample @sample-app"
        body = f"# Sample\r\n\r\n## active {STAGE}\r\n\r\nTodo:\r\n- [/] {original}\r\n    - Artifact: C1"
        self.log.write_bytes(body.encode())
        self.split(("Develop: first result @sample-app", "Verify: second result @sample-app"), task=original)
        current = self.log.read_bytes()
        self.assertNotIn(b"\n", current.replace(b"\r\n", b""))
        self.assertIn(b"    - Artifact: C1\r\n    - Resolution:", current)
        self.assertEqual(self.cli('log', 'check', "log.md", code=1)[0]["code"], "STAGE_EMOJI")
