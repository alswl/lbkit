import importlib.util
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('bump', Path(__file__).parents[1] / 'scripts/bump.py')
bump = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bump)


class BumpTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / 'VERSION').write_text('0.4.1-dev\n')
        skill = self.root / 'skills/lb-plan/SKILL.md'
        skill.parent.mkdir(parents=True)
        skill.write_text('---\nname: lb-plan\nversion: 0.4.1-dev\n---\nversion: preserve\n')
        (self.root / 'pyproject.toml').write_text('[project]\nname = "lbkit"\nversion = "0.4.1.dev0"\n[tool.other]\nversion = "7"\n')
        (self.root / 'uv.lock').write_text('version = 1\n[[package]]\nname = "lbkit"\nversion = "0.4.1.dev0"\n[[package]]\nname = "other"\nversion = "7"\n')
        (self.root / 'schema.json').write_text('{"version": 1}\n')
        (self.root / 'unrelated.md').write_text('human work\n')

    def snapshot(self):
        return {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def test_scope_increments_preserve_stage(self):
        for target, expected in [('patch', '0.4.2-dev'), ('minor', '0.5.0-dev'), ('major', '1.0.0-dev')]:
            self.assertEqual(expected, bump.target_version('0.4.1-dev', target))
        self.assertEqual('0.5.0', bump.target_version('0.4.1', 'minor'))
        self.assertEqual('0.4.1', bump.target_version('0.4.1-dev', '0.4.1'))

    def test_preview_does_not_write(self):
        before = self.snapshot()
        bump.bump(self.root, 'minor')
        self.assertEqual(before, self.snapshot())

    def test_apply_synchronizes_only_owned_versions(self):
        before = self.snapshot()
        bump.bump(self.root, '0.5.0-dev', apply=True)
        after = self.snapshot()
        self.assertEqual(before.keys(), after.keys())
        for name in ['schema.json', 'unrelated.md']:
            self.assertEqual(before[Path(name)], after[Path(name)])
        self.assertEqual(b'0.5.0-dev\n', after[Path('VERSION')])
        self.assertIn(b'version: 0.5.0-dev', after[Path('skills/lb-plan/SKILL.md')])
        self.assertIn(b'version: preserve', after[Path('skills/lb-plan/SKILL.md')])
        for name in ['pyproject.toml', 'uv.lock']:
            self.assertIn(b'version = "0.5.0.dev0"', after[Path(name)])
            self.assertIn(b'version = "7"', after[Path(name)])

    def test_invalid_target_does_not_write(self):
        before = self.snapshot()
        for target in ['v0.5.0', '01.0.0', '0.5.0.dev0', 'banana']:
            with self.assertRaises(ValueError):
                bump.bump(self.root, target, apply=True)
        self.assertEqual(before, self.snapshot())

    def test_invalid_metadata_does_not_partially_write(self):
        (self.root / 'uv.lock').write_text('version = 1\n')
        before = self.snapshot()
        with self.assertRaises(ValueError):
            bump.bump(self.root, 'minor', apply=True)
        self.assertEqual(before, self.snapshot())

    def test_missing_project_version_cannot_match_tool_version(self):
        (self.root / 'pyproject.toml').write_text('[project]\nname = "lbkit"\n[tool.other]\nversion = "7"\n')
        before = self.snapshot()
        with self.assertRaises(ValueError):
            bump.bump(self.root, 'patch', apply=True)
        self.assertEqual(before, self.snapshot())
