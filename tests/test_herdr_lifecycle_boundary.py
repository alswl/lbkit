"""Herdr lifecycle commands must identify their backend explicitly."""

import unittest

from click.testing import CliRunner

from logbook_cli.cli import app


class HerdrLifecycleBoundaryTest(unittest.TestCase):
    def test_backend_lifecycle_is_discoverable_under_agent_herdr(self):
        for command in ("open", "close-session"):
            with self.subTest(command=command):
                result = CliRunner().invoke(app, ["agent", "herdr", command, "--help"])
                self.assertEqual(result.exit_code, 0, result.output)
                self.assertIn("--input-file", result.output)

    def test_backend_lifecycle_has_no_generic_compatibility_alias(self):
        for command in ("open", "close-session"):
            with self.subTest(command=command):
                result = CliRunner().invoke(app, ["agent", command, "--help"])
                self.assertEqual(result.exit_code, 2, result.output)
                self.assertIn("No such command", result.output)
