"""Setup assessment with explicit runtime discovery facts and offline guidance."""

import os
from unittest.mock import patch

from coordination_helpers import CoordinationTest

from logbook_cli.services import skill_capabilities

BUNDLED = "---\nname: herdr\n---\n# Herdr\nUse supported controls.\n"


class HerdrReadinessTest(CoordinationTest):
    def setUp(self):
        super().setUp()
        self.assertTrue(
            callable(getattr(skill_capabilities, "herdr_readiness", None)),
            "T053 separate Herdr setup assessment is not implemented",
        )
        self.installed = self.root / ".agents/skills/herdr/SKILL.md"
        self.installed.parent.mkdir(parents=True)
        self.script(
            [
                {"argv": ["--skill"], "responses": [{"stdout": BUNDLED}]},
                {
                    "argv": ["integration", "status"],
                    "responses": [
                        {"stdout": {"result": {"codex": "ready", "claude": "outdated"}}}
                    ],
                },
                {
                    "argv": ["status"],
                    "responses": [{"stdout": {"result": {"running": True}}}],
                },
            ]
        )

    def assess(self, runtime="codex", verified=True, names=None):
        discovery = {
            "paths": [str(self.installed)],
            "names": ["herdr"] if names is None else names,
            "verified": verified,
        }
        with patch.dict(os.environ, self.env):
            return skill_capabilities.herdr_readiness(self.root, runtime, discovery)

    def test_retrievable_guidance_does_not_mean_installed(self):
        result = self.assess()
        self.assertEqual(result["skill"]["status"], "missing")
        self.assertFalse(self.installed.exists())

    def test_stale_customization_is_reported_without_overwrite(self):
        self.installed.write_text(BUNDLED + "Local customization\n")
        before = self.snapshot()
        self.assertEqual(self.assess()["skill"]["status"], "stale")
        self.assertEqual(before, self.snapshot())

    def test_current_skill_is_independent_of_runtime_integration(self):
        self.installed.write_text(BUNDLED)
        result = self.assess("claude")
        self.assertEqual(result["skill"]["status"], "current")
        self.assertEqual(result["integration"]["status"], "outdated")
        self.assertNotEqual(result["session"]["status"], "ready")

    def test_current_and_discoverable_is_not_session_readiness(self):
        self.installed.write_text(BUNDLED)
        result = self.assess()
        self.assertEqual(result["skill"]["status"], "current")
        self.assertEqual(result["integration"]["status"], "ready")
        self.assertEqual(result["session"]["status"], "unknown")

    def test_unknown_discovery_is_not_guessed_from_a_readable_file(self):
        self.installed.write_text(BUNDLED)
        self.assertEqual(self.assess(verified=False)["skill"]["status"], "unknown")

    def test_unlisted_skill_is_not_discoverable(self):
        self.installed.write_text(BUNDLED)
        self.assertEqual(self.assess(names=[])["skill"]["status"], "undiscoverable")

    def test_configured_unreadable_skill_is_not_ready(self):
        self.installed.mkdir()
        result = self.assess()
        self.assertEqual(result["skill"]["status"], "unreadable")
        self.assertTrue(self.installed.is_dir())
