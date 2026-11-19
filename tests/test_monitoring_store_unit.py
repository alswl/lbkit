import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from herdr_fixtures import target

from logbook_cli import observation, unified, wait_state
from logbook_cli.document import LbError


class MonitoringTests(unittest.TestCase):
    def test_first_empty_configuration_is_complete(self):
        doc = SimpleNamespace(metadata={"document": {"identity": {"uuid": "a" * 32}}})
        with (
            patch.object(observation, "_snapshot", return_value=(None, "token", None)),
            patch.object(observation, "scope", return_value=Path("/repo/lb/work.json")),
        ):
            result = observation._configure(doc, [], [], "token", True)
        value = result["observation"]
        self.assertEqual(value["targets"], [])
        self.assertEqual(value["cursors"], [])
        self.assertEqual(value["retired"], {})
        self.assertEqual(value["revision"], 1)
        observation.validate(value)

    def historical_monitoring(self):
        active = target()
        cursor = wait_state.initial(active) | {
            "sequence": 11,
            "reported": "needs_input",
        }
        return {
            "format": "lb-observation",
            "id": "a" * 32,
            "targets": [active],
            "contexts": [cursor],
            "target_revision": 17,
            "events": [{"id": "event-1", "history": [{"id": "action-1"}]}],
            "answers": [{"id": "answer-1", "event_id": "event-1"}],
            "retired": {"previous": {"target": active, "context": cursor}},
            "listener": {
                "invocation_id": "listener-1",
                "status": "ended",
                "generation": 3,
            },
        }

    def test_legacy_import_renames_only_the_top_level_fields(self):
        old = self.historical_monitoring()
        original = observation.encode(old)
        expected = old.copy()
        expected["cursors"] = expected.pop("contexts")
        expected["revision"] = expected.pop("target_revision")
        self.assertEqual(observation.decode_for_migration(original), expected)
        self.assertEqual(
            observation.decode_for_migration(observation.encode(expected)), expected
        )
        self.assertEqual(observation.encode(old), original)

    def test_migration_refuses_mixed_incomplete_and_invalid_field_pairs(self):
        old = self.historical_monitoring()
        without_contexts = {
            key: value for key, value in old.items() if key != "contexts"
        }
        without_revision = {
            key: value for key, value in old.items() if key != "target_revision"
        }
        cases = (
            (old | {"cursors": old["contexts"]}, "ambiguous observation schema"),
            (
                old | {"revision": old["target_revision"]},
                "ambiguous observation schema",
            ),
            (
                without_contexts | {"cursors": old["contexts"]},
                "ambiguous observation schema",
            ),
            (
                without_revision | {"revision": old["target_revision"]},
                "ambiguous observation schema",
            ),
            (without_contexts, "incomplete legacy observation field pair"),
            (without_revision, "incomplete legacy observation field pair"),
            (old | {"target_revision": True}, "invalid observation revision"),
            (old | {"target_revision": -1}, "invalid observation revision"),
            (old | {"contexts": []}, "invalid observation cursors"),
        )
        for value, message in cases:
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, message):
                observation.decode_for_migration(observation.encode(value))
        with self.assertRaisesRegex(ValueError, "duplicate JSON key: target_revision"):
            observation.decode_for_migration(
                b'{"target_revision": 17, "target_revision": 17}'
            )

    def test_unified_reader_rejects_legacy_and_mixed_monitoring_fields(self):
        old = self.historical_monitoring()
        current = observation.decode_for_migration(observation.encode(old))
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "sample.json"
            envelope = {
                "format": unified.FORMAT,
                "identity": {
                    "run_id": "b" * 32,
                    "log_path": "sample.md",
                    "document_paths": ["sample.md"],
                },
                "documents": {},
                "execution": {"tasks": {}, "operations": {}, "facts": []},
                "monitoring": current,
            }
            path.write_bytes(unified.encode(envelope))
            self.assertEqual(unified.read(path)["monitoring"], current)
            mixed = current | {
                "contexts": current["cursors"],
                "target_revision": current["revision"],
            }
            for value in (old, mixed):
                with self.subTest(value=value):
                    path.write_bytes(unified.encode(envelope | {"monitoring": value}))
                    with self.assertRaisesRegex(
                        LbError, "legacy observation fields"
                    ) as caught:
                        unified.read(path)
                    self.assertEqual(caught.exception.code, 4)
