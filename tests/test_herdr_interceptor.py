"""Behavior contract for the proposed thin Herdr configuration interceptor."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from click.testing import CliRunner

from logbook_cli.cli import app

FAKE = """import json, os, sys
from pathlib import Path
p = Path(os.environ["INTERCEPTOR_FIXTURE"])
data = json.loads(p.read_text())
index = len(data["calls"])
args = sys.argv[1:]
data["calls"].append(args)
p.write_text(json.dumps(data))
step = data["steps"][index] if index < len(data["steps"]) else {}
if step.get("args") != args:
    sys.stderr.write("fixture unexpected argv: " + repr(args))
    sys.exit(90)
sys.stdout.buffer.write(bytes.fromhex(step["stdout_hex"]) if "stdout_hex" in step else step.get("stdout", "").encode())
sys.stderr.buffer.write(bytes.fromhex(step["stderr_hex"]) if "stderr_hex" in step else step.get("stderr", "").encode())
sys.exit(step.get("code", 0))
"""


class HerdrInterceptorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(
            prefix="interceptor-", dir=os.getenv("TMPDIR")
        )
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.fixture = self.root / "calls.json"
        self.binary = self.root / "herdr"
        self.binary.write_text(f"#!{sys.executable}\n" + FAKE)
        self.binary.chmod(0o700)
        self.config("qa-")
        self.env = {
            "PATH": str(self.root) + os.pathsep + os.environ.get("PATH", ""),
            "INTERCEPTOR_FIXTURE": str(self.fixture),
            "HERDR_ENV": "1",
        }
        self.created = (
            json.dumps(
                {
                    "result": {
                        "tab": {"tab_id": "w1:t2", "label": "qa-worker"},
                        "root_pane": {"pane_id": "w1:p2"},
                    }
                }
            )
            + "\n"
        )

    def config(self, prefix):
        (self.root / "lbkit.yaml").write_text(
            json.dumps(
                {
                    "version": "0.2.0",
                    "settings": {
                        "runtime": {
                            "herdr": {
                                "label_prefix": prefix,
                            }
                        }
                    },
                    "agents": {},
                }
            )
        )

    def steps(self, *steps):
        self.fixture.write_text(json.dumps({"steps": steps, "calls": []}))

    def calls(self):
        return json.loads(self.fixture.read_text())["calls"]

    def invoke(self, *args, binary=False):
        result = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve().parents[1] / "bin/lb"),
                "--root",
                str(self.root),
                "herdr",
                "--",
                *args,
            ],
            env={**os.environ, **self.env},
            capture_output=True,
            text=not binary,
        )
        return SimpleNamespace(
            exit_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            output=result.stdout + result.stderr,
        )

    def test_native_failure_preserves_non_utf8_bytes(self):
        argv = ["tab", "create", "--label", "qa-worker"]
        self.steps(
            {"args": argv, "stdout_hex": "ff0061", "stderr_hex": "fe0062", "code": 23}
        )
        result = self.invoke("tab", "create", "--label", "worker", binary=True)
        self.assertEqual(
            (result.exit_code, result.stdout, result.stderr),
            (23, b"\xff\x00a", b"\xfe\x00b"),
        )
        self.assertEqual(self.calls(), [argv])

    def test_approved_wrapper_command_is_forwarded_literally_without_allocation(self):
        (self.root / "lbkit.yaml").unlink()
        argv = ["pane", "run", "w1:p9", " approved-runner --model 'example model'"]
        self.steps({"args": argv, "stdout": "native\n"})
        result = self.invoke(*argv)
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(self.calls(), [argv])

    def test_opaque_managed_creation_forwards_without_policy_or_readback(self):
        (self.root / "lbkit.yaml").unlink()
        argv = ["tab", "create", "--future-option", "value", "--no-focus"]
        self.steps(
            {
                "args": argv,
                "stdout": "native-out\n",
                "stderr": "native-err\n",
                "code": 23,
            }
        )
        result = self.invoke(*argv)
        self.assertEqual((result.exit_code, result.stdout), (23, "native-out\n"))
        self.assertIn("configuration_not_applied", result.stderr)
        self.assertTrue(result.stderr.endswith("native-err\n"))
        self.assertEqual(self.calls(), [argv])

    def tab_steps(self, argv, actual="qa-worker", globals_=()):
        read = json.dumps({"result": {"tab": {"tab_id": "w1:t2", "label": actual}}})
        self.steps(
            {"args": list(globals_) + argv, "stdout": self.created},
            {"args": list(globals_) + ["tab", "get", "w1:t2"], "stdout": read},
        )

    def test_native_fixture_control_preserves_exit_and_streams(self):
        self.steps(
            {
                "args": ["future", "op"],
                "stdout": "native-out\n",
                "stderr": "native-err\n",
                "code": 23,
            }
        )
        result = subprocess.run(
            [str(self.binary), "future", "op"],
            env={**os.environ, **self.env},
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            (result.returncode, result.stdout, result.stderr),
            (23, "native-out\n", "native-err\n"),
        )

    def test_configuration_control_accepts_custom_prefix(self):
        result = CliRunner().invoke(
            app, ["--root", str(self.root), "config", "resolve", "--json"]
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(
            json.loads(result.stdout)["settings"]["runtime"]["herdr"]["label_prefix"],
            "qa-",
        )

    def test_unknown_command_forwards_exact_argv_without_config(self):
        (self.root / "lbkit.yaml").unlink()
        argv = ["future", "op", "--label", "x y", "$(literal)"]
        self.steps({"args": argv, "stdout": "native\n"})
        result = self.invoke(*argv)
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual((result.stdout, self.calls()), ("native\n", [argv]))

    def test_native_failure_preserves_both_streams_and_exit(self):
        self.steps(
            {"args": ["status"], "stdout": "out\n", "stderr": "err\n", "code": 23}
        )
        result = self.invoke("status")
        self.assertEqual(
            (result.exit_code, result.stdout, result.stderr), (23, "out\n", "err\n")
        )

    def test_tab_create_applies_prefix_and_verifies_owned_tab(self):
        argv = [
            "tab",
            "create",
            "--workspace",
            "w1",
            "--label",
            "qa-worker",
            "--no-focus",
        ]
        self.tab_steps(argv)
        result = self.invoke(
            "tab", "create", "--workspace", "w1", "--label", "worker", "--no-focus"
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(result.stdout, self.created)
        self.assertEqual(self.calls(), [argv, ["tab", "get", "w1:t2"]])

    def test_label_equals_form_remains_literal_for_native_syntax_validation(self):
        label = "qa-worker $(literal)"
        argv = [
            "tab",
            "create",
            "--label=" + label,
            "--cwd",
            "/example/work tree",
            "--no-focus",
        ]
        self.tab_steps(argv, actual=label)
        result = self.invoke(
            "tab",
            "create",
            "--label=worker $(literal)",
            "--cwd",
            "/example/work tree",
            "--no-focus",
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(self.calls()[0], argv)

    def test_existing_prefix_is_not_added_twice(self):
        argv = ["tab", "create", "--label", "qa-worker", "--no-focus"]
        self.tab_steps(argv)
        result = self.invoke(*argv)
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(self.calls()[0], argv)

    def test_prefix_starting_with_dash_remains_label_data(self):
        self.config("-qa-")
        argv = ["tab", "create", "--label", "-qa-worker", "--no-focus"]
        self.tab_steps(argv, actual="-qa-worker")
        result = self.invoke("tab", "create", "--label", "worker", "--no-focus")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(self.calls()[0], argv)

    def test_empty_prefix_preserves_native_behavior_without_readback(self):
        self.config("")
        argv = ["tab", "create", "--label", "worker", "--no-focus"]
        self.steps({"args": argv, "stdout": self.created})
        result = self.invoke(*argv)
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(self.calls(), [argv])

    def test_option_value_cannot_be_mistaken_for_subcommand(self):
        argv = ["agent", "prompt", "reviewer", "tab create --label worker"]
        self.steps({"args": argv, "stdout": "native\n"})
        result = self.invoke(*argv)
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(self.calls(), [argv])

    def test_machine_selector_is_preserved_on_create_and_readback(self):
        argv = ["tab", "create", "--label", "qa-worker", "--no-focus"]
        self.tab_steps(argv, globals_=["--machine", "test-machine"])
        result = self.invoke(
            "--machine",
            "test-machine",
            "tab",
            "create",
            "--label",
            "worker",
            "--no-focus",
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(
            self.calls()[1], ["--machine", "test-machine", "tab", "get", "w1:t2"]
        )

    def test_label_mismatch_preserves_created_id_without_retry(self):
        argv = ["tab", "create", "--label", "qa-worker", "--no-focus"]
        self.tab_steps(argv, actual="worker")
        result = self.invoke("tab", "create", "--label", "worker", "--no-focus")
        self.assertEqual(result.exit_code, 4, result.output)
        self.assertEqual(result.stdout, self.created)
        self.assertIn("label_mismatch", result.stderr)
        self.assertIn("w1:t2", result.stderr)
        self.assertEqual(len(self.calls()), 2)

    def test_missing_resource_identity_never_recreates(self):
        argv = ["tab", "create", "--label", "qa-worker", "--no-focus"]
        self.steps({"args": argv, "stdout": '{"result": {}}\n'})
        result = self.invoke("tab", "create", "--label", "worker", "--no-focus")
        self.assertEqual(result.exit_code, 4, result.output)
        self.assertIn("identity_missing", result.stderr)
        self.assertEqual(self.calls(), [argv])

    def test_default_tab_name_is_read_then_renamed_and_verified(self):
        argv = ["tab", "create", "--no-focus"]

        def tab(label):
            return json.dumps({"result": {"tab": {"tab_id": "w1:t2", "label": label}}})

        for base in ("Shell", ""):
            with self.subTest(base=base):
                self.steps(
                    {"args": argv, "stdout": self.created},
                    {"args": ["tab", "get", "w1:t2"], "stdout": tab(base)},
                    {"args": ["tab", "rename", "w1:t2", "qa-" + base], "stdout": "{}"},
                    {"args": ["tab", "get", "w1:t2"], "stdout": tab("qa-" + base)},
                )
                result = self.invoke(*argv)
                self.assertEqual(result.exit_code, 0, result.output)
                self.assertEqual(len(self.calls()), 4)

    def test_pane_name_uses_label_title_or_id_and_preserves_selectors(self):
        for fields, base in (
            ({"label": "custom", "title": "ignored"}, "custom"),
            ({"label": None, "title": "Shell"}, "Shell"),
            ({"terminal_title_stripped": "terminal"}, "terminal"),
            ({}, "w1:p2"),
        ):
            with self.subTest(fields=fields):
                selectors = ["--machine=fixture", "--session", "example"]
                argv = selectors + [
                    "pane",
                    "split",
                    "--pane",
                    "w1:p9",
                    "--env",
                    "A=x y",
                    "--no-focus",
                ]

                def pane(extra):
                    return json.dumps(
                        {"result": {"pane": {"pane_id": "w1:p2", **extra}}}
                    )

                self.steps(
                    {"args": argv, "stdout": pane({})},
                    {
                        "args": selectors + ["pane", "get", "w1:p2"],
                        "stdout": pane(fields),
                    },
                    {
                        "args": selectors + ["pane", "rename", "w1:p2", "qa-" + base],
                        "stdout": "{}",
                    },
                    {
                        "args": selectors + ["pane", "get", "w1:p2"],
                        "stdout": pane({"label": "qa-" + base}),
                    },
                )
                result = self.invoke(*argv)
                self.assertEqual(result.exit_code, 0, result.output)
                self.assertEqual(len(self.calls()), 4)

    def test_ambiguous_arguments_follow_b_without_reading_invalid_config(self):
        self.config(["invalid"])
        for args in (
            ["--label"],
            ["--label", "a", "--label=b"],
            ["--focus", "--no-focus"],
            ["--cwd", "--no-focus"],
        ):
            with self.subTest(args=args):
                argv = ["tab", "create", *args]
                self.steps({"args": argv, "stdout": "native\n"})
                result = self.invoke(*argv)
                self.assertEqual(result.exit_code, 0, result.output)
                self.assertIn("configuration_not_applied", result.stderr)
                self.assertEqual(self.calls(), [argv])

    def test_native_creation_failure_does_not_read_or_rename(self):
        argv = ["tab", "create", "--label", "qa-worker", "--focus"]
        self.steps(
            {"args": argv, "stdout": "partial\n", "stderr": "refused\n", "code": 19}
        )
        result = self.invoke("tab", "create", "--label", "worker", "--focus")
        self.assertEqual(
            (result.exit_code, result.stdout, result.stderr),
            (19, "partial\n", "refused\n"),
        )
        self.assertEqual(self.calls(), [argv])

    def test_rename_or_read_failure_preserves_original_created_id(self):
        for stage in ("rename", "read"):
            with self.subTest(stage=stage):
                argv = ["pane", "split", "w1:p9", "--no-focus"]
                pane = json.dumps(
                    {"result": {"pane": {"pane_id": "w1:p2", "label": "Shell"}}}
                )
                steps = [
                    {"args": argv, "stdout": pane},
                    {"args": ["pane", "get", "w1:p2"], "stdout": pane},
                ]
                if stage == "rename":
                    steps.append(
                        {"args": ["pane", "rename", "w1:p2", "qa-Shell"], "code": 9}
                    )
                else:
                    steps += [
                        {
                            "args": ["pane", "rename", "w1:p2", "qa-Shell"],
                            "stdout": "{}",
                        },
                        {"args": ["pane", "get", "w1:p2"], "code": 9},
                    ]
                self.steps(*steps)
                result = self.invoke(*argv)
                self.assertEqual(result.exit_code, 4, result.output)
                self.assertEqual(result.stdout, pane)
                self.assertIn("w1:p2", result.stderr)
                self.assertEqual(
                    sum(c[:2] == ["pane", "split"] for c in self.calls()), 1
                )

    def test_missing_or_invalid_configuration_prevents_managed_creation(self):
        for invalid in (False, True):
            with self.subTest(invalid=invalid):
                if invalid:
                    self.config(["invalid"])
                else:
                    (self.root / "lbkit.yaml").unlink()
                self.steps()
                result = self.invoke("tab", "create", "--label", "worker")
                self.assertEqual(result.exit_code, 4, result.output)
                self.assertEqual(self.calls(), [])

    def test_empty_argv_is_usage_error_without_launch(self):
        self.steps()
        result = self.invoke()
        self.assertEqual(result.exit_code, 2, result.output)
        self.assertEqual(self.calls(), [])


if __name__ == "__main__":
    unittest.main()
