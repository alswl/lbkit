"""Shared read-only binding checks for lifecycle and waiting."""

import unittest

from herdr_fixtures import observation, target

from logbook_cli.adapters import herdr
from logbook_cli.document import LbError


class BindingTest(unittest.TestCase):
    def test_native_identity_and_topology_are_verified(self):
        item = target()
        value = observation(item, "idle")
        result = herdr.binding_observation(item["binding"], value, value)
        self.assertEqual(result["binding"], item["binding"])
        self.assertEqual(result["state"], "idle")

    def test_changed_session_remains_changed(self):
        item = target()
        changed = target()
        changed["binding"]["session_id"] = "new-native"
        value = observation(changed, "idle")
        result = herdr.binding_observation(item["binding"], value, value)
        self.assertNotEqual(result["binding"], item["binding"])

    def test_unverified_identity_is_not_filled_from_request(self):
        with self.assertRaises(LbError):
            herdr.binding_observation(target()["binding"], {}, {})
