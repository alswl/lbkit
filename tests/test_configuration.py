"""Atomic YAML configuration behavior and public discovery."""

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from click.testing import CliRunner

from logbook_cli import configuration as cfg
from logbook_cli.cli import app as lb
from logbook_cli.document import LbError

KIT = Path(__file__).resolve().parents[1]
AGENT = {
    "launcher": {"command": "example-runner", "args": []},
    "model": "example-model",
    "deployment": "external",
    "suitable_for": ["local editing"],
}
RECIPE = {
    "applies_to": ["documentation"],
    "excludes": ["deployment"],
    "steps": ["example-docs"],
    "companions": [],
    "description": "Human description",
}


class ConfigurationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "lbkit.yaml"
        self.path.write_bytes((KIT / "lbkit.template.yaml").read_bytes())
        self.skills = self.root / "lbkit-skills.yaml"
        self.skills.write_bytes((KIT / "lbkit-skills.template.yaml").read_bytes())
        self.runner = CliRunner()

    def token(self, name="lbkit.yaml"):
        return cfg.digest((self.root / name).read_bytes())

    def write_input(self, payload):
        (self.root / "input.yaml").write_bytes(cfg.encode(payload))
        return "input.yaml"

    def mutate(self, group, action, identity, payload=None, **kwargs):
        return cfg.mutate(
            self.root,
            group,
            action,
            identity,
            payload or {},
            kwargs.get("token", self.token(cfg.GROUPS[group])),
            kwargs.get("dry_run", False),
        )

    def test_create_preview_cas_and_preservation(self):
        self.path.write_text(
            self.path.read_text() + '# Human notes\ncustom: "原文" # preserve\n'
        )
        before = self.path.read_bytes()
        self.mutate("agents", "create", "local-builder", AGENT, dry_run=True)
        self.assertEqual(before, self.path.read_bytes())
        token = self.token()
        self.mutate("agents", "create", "local-builder", AGENT)
        self.assertIn('# Human notes\ncustom: "原文" # preserve', self.path.read_text())
        after = self.path.read_bytes()
        with self.assertRaises(LbError):
            self.mutate(
                "agents", "update", "local-builder", {"model": "other"}, token=token
            )
        self.assertEqual(after, self.path.read_bytes())
        self.mutate(
            "agents", "update", "local-builder", {"launcher": {"command": "other"}}
        )
        self.assertEqual(
            cfg.read(self.root)[2]["agents"]["local-builder"]["launcher"]["args"], []
        )

    def test_lifecycle_reenable_and_default_reference(self):
        self.mutate("agents", "create", "builder", AGENT)
        self.mutate("recipes", "create", "docs", RECIPE)
        self.mutate("recipes", "set-status", "docs", {"status": "available"})
        self.mutate("agents", "set-status", "builder", {"status": "available"})
        self.mutate("agents", "set-status", "builder", {"status": "deprecated"})
        self.mutate("agents", "set-status", "builder", {"status": "retired"})
        self.mutate("agents", "set-status", "builder", {"status": "draft"})
        self.mutate("agents", "set-status", "builder", {"status": "available"})
        with self.assertRaises(LbError):
            self.mutate("agents", "update", "builder", {"status": "retired"})
        with self.assertRaises(LbError):
            self.mutate("agents", "remove", "builder")

    def test_resolve_provenance_is_read_only(self):
        self.mutate("agents", "create", "builder", AGENT)
        self.mutate("agents", "set-status", "builder", {"status": "available"})
        before = self.path.read_bytes()
        result = cfg.resolve(
            self.root, "builder", {"settings": {"limits": {"wait_seconds": 7}}}
        )
        self.assertEqual(result["sources"]["default_agent"], "--agent")
        self.assertEqual(
            result["sources"]["limits.wait_seconds"], "input_file:settings"
        )
        self.assertEqual(result["settings"]["limits"]["context_unknown_packages"], 3)
        self.assertEqual(result["execution"], "none")
        self.assertEqual(result["agent_source"], "lbkit.yaml:agents.builder")
        self.assertEqual(before, self.path.read_bytes())

    def test_public_commands_and_removed_catalog(self):
        for route in (["config", "agent"], ["config", "recipe"]):
            help_result = self.runner.invoke(lb, [*route, "--help"])
            for name in ["list", "show", "create", "update", "set-status", "remove"]:
                self.assertIn(name, help_result.output)
        result = self.runner.invoke(lb, ["skill", "catalog"])
        self.assertNotEqual(result.exit_code, 0)
        inp = self.write_input(RECIPE)
        result = self.runner.invoke(
            lb,
            [
                "config",
                "recipe",
                "create",
                "docs",
                "--root",
                str(self.root),
                "--input-file",
                inp,
                "--expect-version",
                self.token("lbkit-skills.yaml"),
            ],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("docs", cfg.read(self.root, cfg.SKILLS_NAME)[2]["recipes"])
        self.assertNotIn("recipes", cfg.read(self.root)[2])

    def test_skills_file_is_optional_for_reads_and_required_for_writes(self):
        self.skills.unlink()
        self.assertEqual(cfg.read(self.root, cfg.SKILLS_NAME)[2]["recipes"], {})
        self.assertIsNone(cfg.snapshot(self.root)["skills"]["version_token"])
        with self.assertRaises(LbError):
            cfg.mutate(self.root, "recipes", "create", "docs", RECIPE, None, False)
        self.assertFalse(self.skills.exists())

    def test_validation(self):
        original = cfg.read(self.root)[2]
        for mutate in [
            lambda v: v.update(version="99"),
            lambda v: v["settings"].update(default_agent="missing"),
            lambda v: v["settings"].update(default_agent=[]),
            lambda v: v["agents"].update(bad={"status": []}),
        ]:
            value = copy.deepcopy(original)
            mutate(value)
            with self.assertRaises(LbError):
                cfg.validate(value)
        with self.assertRaises(LbError):
            cfg.decode(b"version: one\nversion: two\n")

    def test_concurrent_writers_only_one_wins(self):
        self.mutate("agents", "create", "builder", AGENT)
        token = self.token()
        args = [
            sys.executable,
            str(KIT / "bin/lb"),
            "config",
            "agent",
            "update",
            "builder",
            "--root",
            str(self.root),
            "--expect-version",
            token,
        ]
        (self.root / "a.yaml").write_text("model: model-a\n")
        (self.root / "b.yaml").write_text("model: model-b\n")
        processes = [
            subprocess.Popen(
                [*args, "--input-file", name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            for name in ["a.yaml", "b.yaml"]
        ]
        for proc in processes:
            proc.communicate(timeout=20)
        self.assertEqual(sorted(p.returncode for p in processes), [0, 4])
        self.assertIn(
            cfg.read(self.root)[2]["agents"]["builder"]["model"],
            ["model-a", "model-b"],
        )

    def test_settings_patch_and_default_reference(self):
        self.mutate("agents", "create", "builder", AGENT)
        self.mutate("agents", "set-status", "builder", {"status": "available"})
        inp = self.write_input({"settings": {"default_agent": "builder"}})
        result = self.runner.invoke(
            lb,
            [
                "config",
                "update",
                "--root",
                str(self.root),
                "--input-file",
                inp,
                "--expect-version",
                self.token(),
            ],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        with self.assertRaises(LbError):
            self.mutate("agents", "set-status", "builder", {"status": "deprecated"})

    def test_roundtrip_is_stable_and_aliases_cannot_mutate_other_objects(self):
        self.mutate("recipes", "create", "docs", RECIPE)
        self.mutate("recipes", "update", "docs", {"description": "Updated"})
        before = self.path.read_bytes()
        self.mutate("recipes", "update", "docs", {"description": "Updated"})
        self.assertEqual(before, self.path.read_bytes())
        for data in [b"a: &a {x: 1}\nb: *a\n", b"a: !!python/object:example {}"]:
            with self.assertRaises(LbError):
                cfg.decode(data)

    def test_takeover_marker_tracks_current_status(self):
        from logbook_cli.document import parse
        from logbook_cli.lifecycle import compact

        path = self.root / "log.md"
        path.write_text(
            "# Example\n\n## 🚧 Stage 01 Build\n\n- [/] Build @core\n    - Status: 👨‍✈️ Captain takeover\n- [ ] Review 👱\n"
        )
        self.assertIn("👨‍✈️ Captain takeover", compact(parse(path, self.root)))
        path.write_text(
            path.read_text().replace("👨‍✈️ Captain takeover", "Sailor execution")
        )
        self.assertNotIn("👨‍✈️", compact(parse(path, self.root)))

    def test_check_returns_structured_invalid_result(self):
        self.path.write_text(
            "version: 0.2.0\nsettings: []\nagents: {}\n"
        )
        result = self.runner.invoke(
            lb, ["config", "check", "--root", str(self.root), "--json"]
        )
        self.assertEqual(result.exit_code, 4)
        self.assertFalse(json.loads(result.output)["valid"])
        with self.assertRaises(LbError):
            cfg.decode(b"false: text\n")


if __name__ == "__main__":
    unittest.main()
