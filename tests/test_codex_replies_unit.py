import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from logbook_cli.adapters.codex_replies import read_reply
from logbook_cli.document import LbError


class CodexReplyTests(TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory()))
        self.cwd = self.root / "repo"
        self.session = "12345678-1234-1234-1234-123456789abc"
        self.journal = (
            self.root / "2026" / "01" / "01" / f"rollout-{self.session}.jsonl"
        )
        self.journal.parent.mkdir(parents=True)
        self.time = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
        self.prompt = "Run the authorized preparation check. Request ID: example"
        self.response = json.dumps(
            {"self_check": "example", "status": "passed", "evidence": "input exists"}
        )
        self.session_meta = {
            "type": "session_meta",
            "payload": {"id": self.session, "cwd": str(self.cwd)},
        }

    def message(self, role, text, *, phase="final_answer", stamp=None):
        return {
            "type": "response_item",
            "timestamp": stamp or self.time.isoformat(),
            "payload": {
                "type": "message",
                "role": role,
                "phase": phase,
                "status": "completed",
                "content": [
                    {
                        "type": "input_text" if role == "user" else "output_text",
                        "text": text,
                    }
                ],
            },
        }

    def lookup(self, *rows):
        self.journal.write_text(
            "".join(json.dumps(row) + "\n" for row in (self.session_meta, *rows))
        )
        return read_reply(
            self.session,
            self.cwd,
            "example",
            hashlib.sha256(self.prompt.encode()).hexdigest(),
            self.time,
            journal_root=self.root,
        )

    def test_only_correlated_final_assistant_reply_counts(self):
        user = self.message("user", self.prompt)
        reply = self.message("assistant", self.response)
        observed = self.lookup(user, reply)
        self.assertEqual(observed.status, "passed")
        self.assertEqual(observed.evidence, "input exists")
        for events in (
            (reply,),
            (user, self.message("user", self.response)),
            (user, self.message("assistant", self.response, phase="commentary")),
            (user, self.message("user", "later request"), reply),
            (
                user,
                self.message("assistant", self.response.replace("example", "other")),
            ),
            (self.message("user", self.prompt, stamp="2026-01-01T11:00:00Z"), reply),
        ):
            with self.subTest(events=events):
                self.assertIsNone(self.lookup(*events))

    def test_journal_identity_and_working_directory_must_match(self):
        self.session_meta["payload"]["cwd"] = str(self.root / "another-repo")
        with self.assertRaisesRegex(LbError, "directory changed"):
            self.lookup(self.message("user", self.prompt))

    def test_channel_requires_session_metadata_even_before_a_reply_exists(self):
        self.journal.touch()
        with self.assertRaisesRegex(LbError, "session metadata"):
            read_reply(
                self.session, self.cwd, "example", "digest", self.time,
                journal_root=self.root,
            )
        self.assertIsNone(self.lookup())
