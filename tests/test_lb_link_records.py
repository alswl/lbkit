"""Offline observation applicability, protected writes and malformed records."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CLI = Path(__file__).resolve().parents[1] / "scripts/lb.py"
URL = "https://sources.example.com/item/1"


class LinkObservationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.log = self.root / "log.md"
        self.log.write_text(f"# Demo\n\n## Overview\n[Reference]({URL})\n\n## 🛫 Stage 01 Demo\n- [ ] Research: item\n    - 来源：[Reference]({URL})\n    - 验收：condition one\n- [ ] Human review: item 👱\n    - Source: [Reference]({URL})\n")

    def cli(self, *args, code=0):
        result = subprocess.run([sys.executable, str(CLI), "--root", str(self.root), *args, "--json"], capture_output=True, text=True)
        self.assertEqual(result.returncode, code, result.stderr + result.stdout)
        return json.loads(result.stdout) if result.returncode in (0, 1) else None

    def context(self):
        return self.cli("context", "log.md")

    def verify(self, line, **kwargs):
        args = ["link", "verify", "log.md", "--line", str(line), "--target", URL, "--label", "Reference", "--observed-at", kwargs.pop("at", "2026-10-14T08:00:00+08:00"), "--observer", "sailor-a", "--basis", "host tool observation", "--token", kwargs.pop("token", self.context()["version_token"])]
        code = kwargs.pop("code", 0)
        for key, value in kwargs.items():
            args.append("--" + key.replace("_", "-"))
            if value is not True:
                args.append(str(value))
        return self.cli(*args, code=code)

    def unchecked(self):
        return [i["line"] for i in self.cli("check", "log.md") if i["code"] == "LINK_UNVERIFIED"]

    def test_overview_and_human_links_require_no_task_or_artifact(self):
        original = self.log.read_bytes()
        token = self.context()["version_token"]
        self.verify(4, dry_run=True)
        self.assertEqual(self.log.read_bytes(), original)
        result = self.verify(4)
        self.assertNotEqual(result["version_token"], token)
        self.assertEqual(self.unchecked(), [8, 11])
        self.verify(11)
        self.assertEqual(self.unchecked(), [8])
        self.assertTrue(self.log.read_bytes().startswith(original))
        self.assertFalse((self.root / "TODO.md").exists())
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ["log.md"])
        self.verify(8, token=token, code=4)

    def test_task_condition_changes_invalidate_but_state_and_line_moves_do_not(self):
        self.verify(8)
        self.assertNotIn(8, self.unchecked())
        self.log.write_text(self.log.read_text().replace("- [ ] Research", "- [/] Research").replace("🛫 Stage", "🚧 Stage"))
        self.assertFalse(self.context()["link_verifications"][0]["invalidation_reason"])
        self.log.write_text("\n" + self.log.read_text())
        self.assertTrue(self.context()["link_verifications"][0]["applicable"])
        self.log.write_text(self.log.read_text().replace("condition one", "condition two"))
        self.assertFalse(self.context()["link_verifications"][0]["applicable"])
        self.assertIn(9, self.unchecked())

    def test_latest_revocation_and_same_time_conflict_remain_unverified(self):
        self.verify(4)
        self.verify(4, outcome="revoked", at="2026-10-14T08:01:00+08:00")
        self.assertIn(4, self.unchecked())
        self.verify(4, outcome="verified", at="2026-10-14T08:01:00+08:00")
        self.assertIn(4, self.unchecked())
        self.verify(4, outcome="verified", at="2026-10-14T08:02:00+08:00")
        self.assertNotIn(4, self.unchecked())

    def test_optional_result_binding_and_validation(self):
        self.verify(4, bind_stage="Stage 01 Demo", code=2)
        self.verify(4, bind_stage="Stage 01 Demo", bind_task="Research: item", result_identity="revision:a")
        self.assertNotIn(4, self.unchecked())
        self.log.write_text(self.log.read_text().replace("condition one", "new condition"))
        self.assertIn(4, self.unchecked())
        self.verify(8, bind_stage="Stage 01 Demo", bind_task="Human review: item 👱", code=4)
        self.verify(4, at="2026-10-14T08:00:00", code=2)

    def test_ambiguous_occurrence_and_unclosed_fence_refuse_without_write(self):
        self.log.write_text(self.log.read_text().replace(f"[Reference]({URL})\n\n##", f"[Reference]({URL})\n[Reference]({URL})\n\n##"))
        before = self.log.read_bytes()
        self.verify(4, code=4)
        self.assertEqual(self.log.read_bytes(), before)
        self.log.write_text(f"# Demo\n\n## Overview\n[Reference]({URL})\n\n```\n")
        before = self.log.read_bytes()
        self.verify(4, code=4)
        self.assertEqual(self.log.read_bytes(), before)

    def test_unterminated_reserved_or_second_comment_cannot_hide_new_metadata(self):
        original = self.log.read_text()
        for suffix in ("<!-- lb-link-verification {}\n", "<!-- closed --> <!-- still open\n", "<!-- first open\n--> <!-- second open\n"):
            with self.subTest(suffix=suffix):
                self.log.write_text(original + "\n" + suffix)
                before = self.log.read_bytes()
                self.verify(4, code=4)
                self.assertEqual(self.log.read_bytes(), before)
                self.assertFalse(self.context()["link_verifications"])

    def test_malformed_hidden_record_and_unrelated_local_link_checks(self):
        self.log.write_text(self.log.read_text() + '\n<!-- lb-link-verification {} -->\n[Missing](missing.md)\n')
        codes = {i["code"] for i in self.cli("check", "log.md", code=1)}
        self.assertTrue({"LINK_VERIFICATION_INVALID", "LOCAL_LINK_MISSING", "LINK_UNVERIFIED"} <= codes)
        self.log.write_text(self.log.read_text().replace('<!-- lb-link-verification {} -->', '```\n<!-- lb-link-verification {} -->\n```'))
        self.assertNotIn("LINK_VERIFICATION_INVALID", {i["code"] for i in self.cli("check", "log.md", code=1)})

    def test_replay_deduplicates_and_html_delimiters_are_escaped(self):
        self.verify(4)
        before = self.log.read_bytes()
        self.verify(4)
        self.assertEqual(self.log.read_bytes(), before)
        self.assertEqual(len(self.context()["link_verifications"]), 1)
