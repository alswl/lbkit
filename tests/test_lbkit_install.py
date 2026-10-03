"""Installer checks that do not create commits or contact a remote."""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


INSTALLER = Path(__file__).resolve().parents[1] / "bin/lbkit"
KIT = INSTALLER.parents[1]


class LbkitInstallTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / "consumer"
        self.repo.mkdir()
        subprocess.run(["git", "-C", str(self.repo), "init", "-q"], check=True)

    def run_install(self, *args, env=None):
        return subprocess.run(
            [str(INSTALLER), "install", "--repo", str(self.repo), "--source", "example.invalid/lbkit.git", *args],
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )

    def prepare_initialized_submodule(self):
        """Stage the working-tree kit as an initialized .lbkit submodule."""
        dest = self.repo / ".lbkit"
        shutil.copytree(KIT, dest, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        sha = subprocess.run(["git", "-C", str(KIT), "rev-parse", "HEAD"], text=True, capture_output=True, check=True).stdout.strip()
        subprocess.run(
            ["git", "-C", str(self.repo), "update-index", "--add", "--cacheinfo", f"160000,{sha},.lbkit"],
            check=True,
        )

    def test_install_initializes_mind_forge_repo_when_mf_available(self):
        self.prepare_initialized_submodule()
        fakebin = Path(self.temp.name) / "fakebin"
        fakebin.mkdir()
        fake = fakebin / "mf"
        fake.write_text(
            '#!/bin/sh\n[ "$1" = init ] || exit 1\nmkdir -p "$2/projects"\nprintf "schema: \'1\'\\nprojects: []\\n" > "$2/minds.yaml"\n',
            encoding="utf-8",
        )
        fake.chmod(0o755)
        result = self.run_install(env=dict(os.environ, PATH=f"{fakebin}:{os.environ['PATH']}"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.repo / "minds.yaml").exists())
        self.assertTrue((self.repo / "projects").is_dir())

    def test_install_reports_missing_mf_without_failing(self):
        self.prepare_initialized_submodule()
        minimal = Path(self.temp.name) / "minimal"
        minimal.mkdir()
        for tool in ("git", "python3"):
            src = shutil.which(tool)
            self.assertIsNotNone(src)
            os.symlink(src, minimal / tool)
        result = self.run_install(env=dict(os.environ, PATH=str(minimal)))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("mf not found", result.stdout)
        self.assertFalse((self.repo / "minds.yaml").exists())

    def test_dry_run_shows_submodule_cli_skills_and_docs_without_writing(self):
        result = self.run_install("--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("git submodule add example.invalid/lbkit.git .lbkit", result.stdout)
        self.assertIn("bin/lbkit -> ../.lbkit/bin/lbkit", result.stdout)
        self.assertIn("bin/lb-anywhere -> ../.lbkit/bin/lb-anywhere", result.stdout)
        self.assertIn(".agents/skills/lb-init -> ../../.lbkit/skills/lb-init", result.stdout)
        self.assertIn("docs/configuration.md -> ../.lbkit/contracts/configuration.md", result.stdout)
        self.assertIn("SKILL-PARAMS.yaml <- .lbkit/SKILL-PARAMS.template.yaml", result.stdout)
        self.assertIn("AGENTS.md <- lbkit stub (fill in local rules)", result.stdout)
        self.assertIn("CLAUDE.md -> AGENTS.md", result.stdout)
        self.assertFalse((self.repo / ".lbkit").exists())
        self.assertFalse((self.repo / ".gitmodules").exists())

    def test_existing_agents_md_is_not_replaced(self):
        (self.repo / "AGENTS.md").write_text("local rules", encoding="utf-8")
        result = self.run_install("--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("AGENTS.md <- lbkit stub", result.stdout)

    def test_existing_skill_refuses_install_before_submodule_add(self):
        skill = self.repo / ".agents/skills/lb-plan"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("local skill", encoding="utf-8")
        result = self.run_install()
        self.assertEqual(result.returncode, 1)
        self.assertIn(".agents/skills/lb-plan", result.stderr)
        self.assertFalse((self.repo / ".lbkit").exists())
        self.assertFalse((self.repo / ".gitmodules").exists())

    def test_unregistered_lbkit_directory_refuses_install(self):
        (self.repo / ".lbkit").mkdir()
        result = self.run_install("--dry-run")
        self.assertEqual(result.returncode, 1)
        self.assertIn("not an indexed submodule", result.stderr)

    def test_anywhere_wrapper_executes_nearest_bin_lb_at_repository_root(self):
        root = Path(self.temp.name) / "proj"
        (root / "deep/nested").mkdir(parents=True)
        stub = root / "bin/lb"
        stub.parent.mkdir()
        stub.write_text('#!/bin/sh\necho "stub cwd=$(pwd) args=$*"\n', encoding="utf-8")
        stub.chmod(0o755)
        wrapper = INSTALLER.parent / "lb-anywhere"
        result = subprocess.run(
            [str(wrapper), "task", "list"],
            cwd=root / "deep/nested",
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), f"stub cwd={root.resolve()} args=task list")

    def test_anywhere_wrapper_fails_outside_a_logbook_repository(self):
        empty = Path(self.temp.name) / "empty"
        empty.mkdir()
        wrapper = INSTALLER.parent / "lb-anywhere"
        result = subprocess.run([str(wrapper)], cwd=empty, text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 1)
        self.assertIn("no bin/lb found", result.stderr)


if __name__ == "__main__":
    unittest.main()
