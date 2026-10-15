import importlib.util
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('release', Path(__file__).parents[1] / 'scripts/release.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        subprocess.run(['git', 'init', '-b', 'master', str(self.root)], check=True, capture_output=True)
        release.git(self.root, 'config', 'user.name', 'Example Maintainer')
        release.git(self.root, 'config', 'user.email', 'maintainer@example.com')
        (self.root / 'VERSION').write_text('0.1.0-dev\n')
        skill = self.root / 'skills/lb-plan/SKILL.md'
        skill.parent.mkdir(parents=True)
        skill.write_text('---\nname: lb-plan\nversion: 0.1.0-dev\n---\nBody\nversion: preserve\n')
        (self.root / 'pyproject.toml').write_text('[project]\nname = "lbkit"\nversion = "0.1.0.dev0"\n')
        (self.root / 'uv.lock').write_text('version = 1\n[[package]]\nname = "lbkit"\nversion = "0.1.0.dev0"\n')
        release.git(self.root, 'add', '.')
        release.git(self.root, 'commit', '-m', 'feat: initial kit')
        self.base = release.git(self.root, 'rev-parse', 'HEAD')

    def test_preview_is_read_only(self):
        release.release(self.root, '0.2.0')
        self.assertEqual(self.base, release.git(self.root, 'rev-parse', 'HEAD'))
        self.assertEqual('', release.git(self.root, 'status', '--porcelain'))
        self.assertEqual('', release.git(self.root, 'tag'))

    def test_release_and_development_metadata(self):
        release.release(self.root, '0.2.0', apply=True)
        self.assertEqual('tag', release.git(self.root, 'cat-file', '-t', 'v0.2.0'))
        self.assertEqual('0.2.0', release.git(self.root, 'show', 'v0.2.0:VERSION'))
        self.assertEqual('0.2.1-dev\n', (self.root / 'VERSION').read_text())
        self.assertIn('version = "0.2.1.dev0"', (self.root / 'uv.lock').read_text())
        self.assertIn('version = "0.2.1.dev0"', (self.root / 'pyproject.toml').read_text())
        self.assertIn('version: 0.2.1-dev', (self.root / 'skills/lb-plan/SKILL.md').read_text())
        self.assertIn('version: preserve', (self.root / 'skills/lb-plan/SKILL.md').read_text())
        self.assertEqual('', release.git(self.root, 'status', '--porcelain'))
        with self.assertRaises(ValueError):
            release.release(self.root, '0.2.0', apply=True)

    def test_historical_tag_does_not_move_master(self):
        release.release(self.root, '0.1.0', apply=True, ref=self.base)
        self.assertEqual(self.base, release.git(self.root, 'rev-parse', 'HEAD'))
        self.assertEqual(self.base, release.git(self.root, 'rev-parse', 'v0.1.0^'))
        self.assertEqual('0.1.0', release.git(self.root, 'show', 'v0.1.0:VERSION'))

    def test_dirty_and_invalid_inputs_are_rejected(self):
        for version in ['v1.0.0', '1.0.0-dev', '01.0.0']:
            with self.assertRaises(ValueError):
                release.release(self.root, version, apply=True)
        with self.assertRaises(ValueError):
            release.release(self.root, '1.0.0', next_dev='0.9.0')
        (self.root / 'untracked').write_text('human work')
        with self.assertRaises(ValueError):
            release.release(self.root, '1.0.0', apply=True)
        self.assertEqual('human work', (self.root / 'untracked').read_text())

    def test_bad_metadata_leaves_refs_unchanged(self):
        (self.root / 'skills/lb-plan/SKILL.md').write_text('---\nname: lb-plan\n---\n')
        release.git(self.root, 'add', '.')
        release.git(self.root, 'commit', '-m', 'test: missing metadata')
        head = release.git(self.root, 'rev-parse', 'HEAD')
        with self.assertRaises(ValueError):
            release.release(self.root, '1.0.0', apply=True)
        self.assertEqual(head, release.git(self.root, 'rev-parse', 'HEAD'))
        self.assertEqual('', release.git(self.root, 'tag'))

    @unittest.skipUnless(shutil.which('git-cliff'), 'git-cliff required')
    def test_changelog_preserves_historical_sections(self):
        source = Path(__file__).parents[1] / 'cliff.toml'
        shutil.copyfile(source, self.root / 'cliff.toml')
        release.git(self.root, 'add', '.')
        release.git(self.root, 'commit', '-m', 'chore: changelog config')
        release.release(self.root, '0.1.0', apply=True, ref=self.base)
        notes = release.git(self.root, 'show', 'v0.1.0:CHANGELOG.md')
        (self.root / 'CHANGELOG.md').write_text(notes + '\n')
        release.git(self.root, 'add', '.')
        release.git(self.root, 'commit', '-m', 'docs: historical releases')
        release.release(self.root, '0.2.0', apply=True)
        notes = (self.root / 'CHANGELOG.md').read_text()
        self.assertIn('## 0.2.0', notes)
        self.assertIn('## 0.1.0', notes)
        self.assertEqual(1, notes.lower().count('initial kit'))
