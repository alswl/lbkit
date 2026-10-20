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
            [
                str(INSTALLER),
                "install",
                "--repo",
                str(self.repo),
                "--source",
                "example.invalid/lbkit.git",
                *args,
            ],
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )

    def prepare_initialized_submodule(self):
        """Stage the working-tree kit as an initialized .lbkit submodule."""
        dest = self.repo / ".lbkit"
        shutil.copytree(
            KIT,
            dest,
            ignore=shutil.ignore_patterns(
                ".git",
                "__pycache__",
                ".venv",
                "dist",
                ".mypy_cache",
                ".ruff_cache",
                ".fude",
            ),
        )
        sha = subprocess.run(
            ["git", "-C", str(KIT), "rev-parse", "HEAD"],
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()
        subprocess.run(
            [
                "git",
                "-C",
                str(self.repo),
                "update-index",
                "--add",
                "--cacheinfo",
                f"160000,{sha},.lbkit",
            ],
            check=True,
        )

    def test_install_initializes_mind_forge_repo_when_mf_available(self):
        self.prepare_initialized_submodule()
        fakebin = Path(self.temp.name) / "fakebin"
        fakebin.mkdir()
        fake = fakebin / "mf"
        fake.write_text(
            '#!/bin/sh\n[ "$1" = version ] && exit 0\n[ "$1" = init ] || exit 1\nmkdir -p "$2/projects"\nprintf "schema: \'1\'\\nprojects: []\\n" > "$2/minds.yaml"\n',
            encoding="utf-8",
        )
        fake.chmod(0o755)
        result = self.run_install(
            env=dict(os.environ, PATH=f"{fakebin}:{os.environ['PATH']}")
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.repo / "minds.yaml").exists())
        self.assertTrue((self.repo / "projects").is_dir())
        self.assertTrue((self.repo / ".lbkit/.venv/bin/python").exists())
        result = subprocess.run(
            [str(self.repo / "bin/lb"), "--version"],
            cwd=self.repo.parent,
            check=False,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), (KIT / "VERSION").read_text().strip())

    def test_runtime_failure_does_not_install_shared_links(self):
        import runpy
        from unittest.mock import patch

        installer = runpy.run_path(str(INSTALLER))
        with (
            patch("shutil.which", return_value=None),
            self.assertRaisesRegex(installer["InstallError"], "uv is required"),
        ):
            installer["install_runtime"](self.repo)
        with (
            patch("shutil.which", return_value="uv"),
            patch(
                "subprocess.run",
                return_value=subprocess.CompletedProcess(
                    [], 1, "", "locked environment failed"
                ),
            ),
            self.assertRaisesRegex(
                installer["InstallError"], "locked environment failed"
            ),
        ):
            installer["install_runtime"](self.repo)
        self.assertFalse((self.repo / ".venv").exists())

    def test_missing_dependencies_give_actionable_error_without_installing(self):
        checkout = self.repo / "kit"
        shutil.copytree(
            KIT / "src", checkout / "src", ignore=shutil.ignore_patterns("__pycache__")
        )
        (checkout / "bin").mkdir()
        shutil.copy2(KIT / "bin/lb", checkout / "bin/lb")
        isolated = self.repo / "empty-env"
        import sys

        subprocess.run(
            [sys.executable, "-m", "venv", "--without-pip", str(isolated)], check=True
        )
        result = subprocess.run(
            [str(isolated / "bin/python"), str(checkout / "bin/lb"), "--help"],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 3)
        self.assertIn("uv sync --locked --no-dev", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertFalse((checkout / ".venv").exists())

    def test_install_refuses_missing_mf_before_writing(self):
        self.prepare_initialized_submodule()
        minimal = Path(self.temp.name) / "minimal"
        minimal.mkdir()
        for tool in ("git", "python3"):
            src = shutil.which(tool)
            self.assertIsNotNone(src)
            os.symlink(src, minimal / tool)
        result = self.run_install(env=dict(os.environ, PATH=str(minimal)))
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("mind-forge is required", result.stderr)
        self.assertFalse((self.repo / "bin").exists())
        self.assertFalse((self.repo / "lbkit-agents.yaml").exists())
        self.assertFalse((self.repo / "minds.yaml").exists())
        (self.repo / "minds.yaml").write_text("schema: '1'\nprojects: []\n")
        result = self.run_install(env=dict(os.environ, PATH=str(minimal)))
        self.assertEqual(result.returncode, 1)
        self.assertIn("mind-forge is required", result.stderr)
        self.assertFalse((self.repo / "bin").exists())

    def test_mf_init_failure_is_not_silently_accepted(self):
        self.prepare_initialized_submodule()
        fakebin = Path(self.temp.name) / "fakebin"
        fakebin.mkdir()
        fake = fakebin / "mf"
        fake.write_text(
            '#!/bin/sh\n[ "$1" = version ] && exit 0\necho "initialization failed" >&2\nexit 1\n'
        )
        fake.chmod(0o755)
        result = self.run_install(
            env=dict(os.environ, PATH=f"{fakebin}:{os.environ['PATH']}")
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("mf init failed", result.stderr)
        self.assertFalse((self.repo / "bin").exists())
        self.assertFalse((self.repo / "minds.yaml").exists())

    def test_dry_run_shows_submodule_cli_skills_and_docs_without_writing(self):
        result = self.run_install("--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            "git submodule add example.invalid/lbkit.git .lbkit", result.stdout
        )
        self.assertIn("bin/lbkit -> ../.lbkit/bin/lbkit", result.stdout)
        self.assertIn("bin/lb-anywhere -> ../.lbkit/bin/lb-anywhere", result.stdout)
        self.assertIn(
            ".agents/skills/lb-init -> ../../.lbkit/skills/lb-init", result.stdout
        )
        self.assertIn(
            "docs/configuration.md -> ../.lbkit/docs/installable/configuration.md",
            result.stdout,
        )
        self.assertIn(
            "lbkit-agents.yaml <- .lbkit/lbkit-agents.template.yaml", result.stdout
        )
        self.assertIn("AGENTS.md <- lbkit stub (fill in local rules)", result.stdout)
        self.assertIn("CLAUDE.md -> AGENTS.md", result.stdout)
        self.assertFalse((self.repo / ".lbkit").exists())
        self.assertFalse((self.repo / ".gitmodules").exists())

    def test_only_shared_contracts_are_installed_and_old_links_migrate(self):
        self.prepare_initialized_submodule()
        docs = self.repo / "docs"
        docs.mkdir()
        old = docs / "configuration.md"
        old.symlink_to("../.lbkit/docs/configuration.md")
        preview = self.run_install("--dry-run")
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertEqual(os.readlink(old), "../.lbkit/docs/configuration.md")
        self.assertNotIn("docs/README.md ->", preview.stdout)
        # Test the link migration independently of the machine's mf installation.
        import runpy

        installer = runpy.run_path(str(INSTALLER))
        mapping = installer["manifest"](self.repo / ".lbkit")
        self.assertEqual(installer["conflicts"](self.repo, mapping), [])
        installer["install_links"](self.repo, mapping)
        self.assertEqual(
            os.readlink(old), "../.lbkit/docs/installable/configuration.md"
        )
        self.assertTrue(old.is_file())
        self.assertFalse((docs / "README.md").exists())
        self.assertFalse((docs / "dev").exists())
        self.assertTrue(
            (self.repo / ".agents/skills/lb-plan/../../docs/installable/coordination.md")
            .resolve()
            .is_file()
        )
        for name in ("lb-takeover", "lb-handoff"):
            for registry in (".agents", ".claude"):
                skill = self.repo / registry / "skills" / name
                self.assertTrue((skill / "SKILL.md").is_file())
                self.assertTrue((skill / "../../docs/installable/coordination.md").resolve().is_file())
            self.assertTrue((self.repo / ".agents/skills" / name / "../lb-push/SKILL.md").resolve().is_file())
        old.unlink()
        old.symlink_to("../user-owned.md")
        self.assertIn(
            Path("docs/configuration.md"), installer["conflicts"](self.repo, mapping)
        )

    def test_retired_link_cleanup_preserves_consumer_content(self):
        import runpy
        installer = runpy.run_path(str(INSTALLER))
        docs = self.repo / "docs"
        docs.mkdir()
        link = docs / "evidence.md"
        for target in ("../.lbkit/docs/evidence.md", "../.lbkit/docs/installable/evidence.md"):
            link.symlink_to(target)
            installer["retire_links"](self.repo, True)
            self.assertTrue(link.is_symlink())
            installer["retire_links"](self.repo, False)
            self.assertFalse(link.is_symlink())
        link.write_bytes(b"consumer-owned\r\n")
        self.assertEqual(installer["retire_links"](self.repo, False), [])
        self.assertEqual(link.read_bytes(), b"consumer-owned\r\n")
        link.unlink()
        link.symlink_to("../user-owned.md")
        installer["retire_links"](self.repo, False)
        self.assertEqual(os.readlink(link), "../user-owned.md")

    def test_retirement_requires_actual_kit_removal_and_safe_parent(self):
        import runpy
        installer = runpy.run_path(str(INSTALLER))
        docs = self.repo / "docs"
        docs.mkdir()
        link = docs / "evidence.md"
        link.symlink_to("../.lbkit/docs/installable/evidence.md")
        target = self.repo / ".lbkit/docs/installable/evidence.md"
        target.parent.mkdir(parents=True)
        target.write_text("still installed")
        self.assertEqual(installer["retire_links"](self.repo, False), [])
        self.assertTrue(link.is_symlink())
        target.unlink()
        installer["retire_links"](self.repo, False)
        self.assertFalse(link.is_symlink())
        docs.rmdir()
        outside = self.repo.parent / "outside"
        outside.mkdir()
        docs.symlink_to(outside, target_is_directory=True)
        (outside / "evidence.md").symlink_to("../.lbkit/docs/installable/evidence.md")
        self.assertEqual(installer["retire_links"](self.repo, False), [])
        self.assertTrue((outside / "evidence.md").is_symlink())

    def test_legacy_agent_config_gets_a_move_hint_only(self):
        legacy = self.repo / ".agents" / "lb.yaml"
        legacy.parent.mkdir()
        legacy.write_text("version: 0.1.0\n", encoding="utf-8")
        result = self.run_install("--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("git mv .agents/lb.yaml lbkit-agents.yaml", result.stdout)
        self.assertNotIn(
            "lbkit-agents.yaml <- .lbkit/lbkit-agents.template.yaml", result.stdout
        )
        self.assertTrue(legacy.exists())
        (self.repo / "lbkit-agents.yaml").write_text(
            "version: 0.1.0\n", encoding="utf-8"
        )
        self.assertNotIn("git mv .agents/lb.yaml", self.run_install("--dry-run").stdout)

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
        self.assertEqual(
            result.stdout.strip(), f"stub cwd={root.resolve()} args=task list"
        )

    def test_anywhere_wrapper_fails_outside_a_logbook_repository(self):
        empty = Path(self.temp.name) / "empty"
        empty.mkdir()
        wrapper = INSTALLER.parent / "lb-anywhere"
        result = subprocess.run(
            [str(wrapper)], cwd=empty, text=True, capture_output=True, check=False
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("no bin/lb found", result.stderr)


if __name__ == "__main__":
    unittest.main()
