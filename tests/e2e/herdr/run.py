"""Explicitly opted-in, real-server/real-agent coordination acceptance."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]


class Blocked(RuntimeError):
    """An observed environment gate prevents the assertion from running."""


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def load_config(path):
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError("configuration must be an object")
    runtimes = value.get("runtimes")
    if not isinstance(runtimes, dict) or not runtimes:
        raise ValueError("configure at least one runtime")
    for name, runtime in runtimes.items():
        if name not in {"codex", "claude"} or not isinstance(runtime, dict):
            raise ValueError("runtime axes must be codex or claude")
        if not isinstance(runtime.get("kind"), str) or not runtime["kind"]:
            raise ValueError("runtime kind required")
        for field in ("args", "startup_keys"):
            args = runtime.get(field, [])
            if not isinstance(args, list) or any(not isinstance(x, str) for x in args):
                raise ValueError(field + " must be an argument array")
    for field in ("startup_timeout", "turn_timeout"):
        duration = value.get(field, 120)
        if type(duration) not in {int, float} or not 0 < duration <= 600:
            raise ValueError(field + " must be in (0, 600]")
    return value


class LiveSuite:
    def __init__(self, config, output, cases=("core", "multi", "captain")):
        self.config = config
        self.cases = set(cases)
        self.output = output
        self.root = output / "workspace"
        self.root.mkdir(parents=True)
        self.owned = []
        self.bindings = {}
        self.cleanup_bindings = {}
        self.checks = []
        self.counter = 0
        self.run_id = uuid.uuid4().hex[:8]
        self.timeout = config.get("turn_timeout", 120)
        # Resolving a venv's executable symlink discards its site-packages.
        self.python = sys.executable
        self.kit = self.root / ".lbkit"
        for directory in ("bin", "src"):
            shutil.copytree(
                REPO / directory,
                self.kit / directory,
                ignore=shutil.ignore_patterns("__pycache__"),
            )
        self.lb = [self.python, str(self.kit / "bin/lb"), "--root", str(self.root)]
        (self.root / "AGENTS.md").write_text(
            "# Disposable integration workspace\n"
            "Follow only the test prompt. Work only in this directory.\n"
            "No installs, commits, network tools or unrelated agent control.\n"
        )
        dump(
            output / "candidate.json",
            {
                str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest()
                for directory in (REPO / "src", REPO / "bin")
                for p in directory.rglob("*")
                if p.is_file() and "__pycache__" not in p.parts
            },
        )

    def command(self, argv, *, timeout=30, expected=(0,)):
        self.counter += 1
        started = time.monotonic()
        try:
            result = subprocess.run(
                argv, cwd=self.root, capture_output=True, text=True, timeout=timeout
            )
        except subprocess.TimeoutExpired as exc:
            dump(
                self.output / "commands" / f"{self.counter:04}.json",
                {
                    "argv": argv,
                    "timeout": timeout,
                    "stdout": self.decode_output(exc.stdout),
                    "stderr": self.decode_output(exc.stderr),
                    "elapsed": time.monotonic() - started,
                },
            )
            raise
        dump(
            self.output / "commands" / f"{self.counter:04}.json",
            {
                "argv": argv,
                "code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "elapsed": time.monotonic() - started,
            },
        )
        if result.returncode not in expected:
            raise AssertionError(
                f"command {self.counter} exited {result.returncode}: "
                + result.stderr[-1500:]
            )
        try:
            return json.loads(result.stdout)
        except ValueError:
            return result.stdout

    @staticmethod
    def decode_output(value):
        return value.decode(errors="replace") if isinstance(value, bytes) else value

    def herdr(self, *args, **kwargs):
        return self.command(["herdr", *args], **kwargs)

    def record(self, name, function):
        from logbook_cli.document import LbError

        started = time.monotonic()
        try:
            detail = function()
            result = {"name": name, "status": "PASS", "detail": detail}
        except Blocked as exc:
            result = {"name": name, "status": "BLOCKED", "detail": str(exc)}
        except (
            AssertionError,
            ValueError,
            KeyError,
            TypeError,
            LbError,
            OSError,
            subprocess.TimeoutExpired,
        ) as exc:
            result = {"name": name, "status": "FAIL", "detail": str(exc)}
        result["elapsed"] = time.monotonic() - started
        self.checks.append(result)
        dump(self.output / "report.json", {"checks": self.checks})
        print(json.dumps(result), flush=True)
        return result["status"] == "PASS"

    def agent(self, pane):
        return self.herdr("agent", "get", pane)["result"]["agent"]

    def binding(self, pane):
        from logbook_cli.adapters.herdr import binding_observation

        observed_pane = self.herdr("pane", "get", pane)["result"]["pane"]
        observed_agent = self.agent(pane)
        return binding_observation(
            {"machine": "local", "server": self.server}, observed_pane, observed_agent
        )

    def read(self, pane):
        try:
            result = self.herdr(
                "agent", "read", pane, "--source", "recent-unwrapped", "--lines", "250"
            )
        except AssertionError:
            # Busy alternate-screen agents may expose only their visible viewport.
            result = self.herdr("agent", "read", pane, "--source", "visible")
        text = result if isinstance(result, str) else json.dumps(result)
        (self.output / f"reply-{pane.replace(':', '-')}.txt").write_text(text)
        return text

    def wait(self, targets, *, after=None, timeout=1, expected=(0,)):
        name = f"wait-{self.counter + 1}.json"
        dump(self.root / name, {"targets": targets, "after": after})
        return self.command(
            [
                *self.lb,
                "agent",
                "wait",
                "--input-file",
                name,
                "--timeout",
                str(timeout),
                "--json",
            ],
            timeout=timeout + 5,
            expected=expected,
        )

    def target(self, axis):
        observed = self.binding(self.bindings[axis]["pane_id"])
        return {
            "binding": observed["binding"],
            "baseline": {
                "state": observed["state"],
                "observed_at": observed["observed_at"],
            },
        }

    def start(self, axis, runtime):
        caller = os.environ["HERDR_PANE_ID"]
        area = self.herdr("pane", "layout", "--pane", caller)["result"]["layout"]
        rect = next(p["rect"] for p in area["panes"] if p["pane_id"] == caller)
        direction = "right" if rect["width"] >= rect["height"] * 2 else "down"
        pane = self.herdr(
            "pane",
            "split",
            caller,
            "--direction",
            direction,
            "--cwd",
            str(self.root),
            "--no-focus",
        )["result"]["pane"]
        pane_id = pane["pane_id"]
        assert pane_id not in self.original_panes, (
            "creation returned a pre-existing pane"
        )
        self.owned.append(pane_id)
        dump(self.output / "owned.json", {"run_id": self.run_id, "panes": self.owned})
        timeout = self.config.get("startup_timeout", 45)
        try:
            self.herdr(
                "agent",
                "start",
                f"lb-e2e-{axis}-{self.run_id}",
                "--kind",
                runtime["kind"],
                "--pane",
                pane_id,
                "--timeout",
                str(int(timeout * 1000)),
                "--",
                *runtime.get("args", []),
                timeout=timeout + 5,
            )
        except AssertionError:
            screen = self.read(pane_id)
            if self.agent(pane_id).get("agent_status") == "blocked":
                raise Blocked("startup dialog: " + screen[-2000:])
            raise
        self.remember_identity(axis, pane_id)
        for key in runtime.get("startup_keys", []):
            self.read(pane_id)
            self.herdr("agent", "send-keys", pane_id, key)
        nonce = f"ACCEPT-{axis}-{self.run_id}"
        self.herdr(
            "agent",
            "prompt",
            pane_id,
            "Local integration test. Do not use tools or access files. "
            "Explicitly accept this harmless instruction by joining these three "
            f"fragments with hyphens and no spaces: ACCEPT, {axis}, {self.run_id}",
            "--wait",
            "--timeout",
            str(int(self.timeout * 1000)),
            timeout=self.timeout + 5,
        )
        assert nonce in self.read(pane_id), "no attributable recipient acceptance"
        observed = self.binding(pane_id)
        self.bindings[axis] = observed["binding"]
        return observed

    def remember_identity(self, axis, pane):
        from logbook_cli.document import LbError

        try:
            self.cleanup_bindings[axis] = self.binding(pane)["binding"]
        except LbError:
            # Some runtimes publish native identity only after their first turn.
            return False
        return True

    def snapshots(self, axis):
        target = self.target(axis)
        first = self.wait([target], timeout=2)
        assert any(e["kind"] == "observation_gap" for e in first["events"]), first
        request = first["next_input"]
        self.continuations[axis] = request
        before = self.business_hashes()
        second = self.wait(request["targets"], after=request["after"], timeout=1)
        assert second["reason"] == "timeout" and not second["events"], second
        assert before == self.business_hashes(), "wait changed business files"
        assert self.target(axis)["binding"] == target["binding"], (
            "Sailor identity changed"
        )
        return {"snapshot": first, "unchanged": second}

    def business_hashes(self):
        return {
            str(p.relative_to(self.root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in self.root.rglob("*")
            if p.is_file()
            and not p.name.startswith("wait-")
            and ".lbkit" not in p.parts
        }

    def invalid(self, axis):
        target = self.target(axis)
        bad = self.wait([target], after="invalid-continuation", expected=(2,))
        changed = {
            **target,
            "binding": {**target["binding"], "session_id": "invalid-test-session"},
        }
        result = self.wait([changed], timeout=2)
        assert [e["kind"] for e in result["events"]] == ["identity_changed"], result
        assert self.target(axis)["binding"] == target["binding"]
        return {"invalid_token": bad, "changed_identity": result}

    def interrupted(self, axis):
        request = self.continuations[axis]
        dump(self.root / "interrupt.json", request)
        process = subprocess.Popen(
            [
                *self.lb,
                "agent",
                "wait",
                "--input-file",
                "interrupt.json",
                "--timeout",
                "30",
                "--json",
            ],
            cwd=self.root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            time.sleep(0.8)
            assert process.poll() is None, "wait returned before interruption"
            process.send_signal(signal.SIGINT)
            stdout, stderr = process.communicate(timeout=4)
            dump(
                self.output / f"interrupt-{axis}.json",
                {"code": process.returncode, "stdout": stdout, "stderr": stderr},
            )
            result = json.loads(stdout)
            assert process.returncode == 130 and result["reason"] == "interrupted", (
                result
            )
            assert self.target(axis)["binding"] == self.bindings[axis]
            return result
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=4)

    def multi(self):
        targets = [self.target(axis) for axis in self.bindings]
        assert len(targets) >= 2, "two real runtimes required"
        result = self.wait(targets, timeout=3)
        assert result["reason"] == "change" and result["events"], result
        for event in result["events"]:
            assert event["binding"] in [t["binding"] for t in targets]
        follow = self.wait(
            result["next_input"]["targets"],
            after=result["next_input"]["after"],
            timeout=1,
        )
        assert all(e["kind"] != "settled" for e in follow["events"]), follow
        return {"first": result, "follow": follow}

    def multi_active(self):
        axes = list(self.bindings)
        assert len(axes) >= 2, "two real runtimes required"
        axes = axes[:2]
        for axis, count in zip(axes, (2500, 150)):
            self.herdr(
                "agent",
                "prompt",
                self.bindings[axis]["pane_id"],
                "Do not use tools. Write every integer from 1 through "
                f"{count} separated by spaces, without abbreviations. Then join "
                f"these fragments with hyphens: MULTI, {axis}, {self.run_id}.",
            )
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            targets = [self.target(axis) for axis in axes]
            if all(t["baseline"]["state"] == "working" for t in targets):
                break
            if any(t["baseline"]["state"] == "blocked" for t in targets):
                raise Blocked("multi-target runtime dialog")
            time.sleep(0.25)
        else:
            raise AssertionError("both targets were never observed working")
        result = self.wait(targets, timeout=self.timeout)
        assert any(e["kind"] == "settled" for e in result["events"]), result
        assert result["pending"], "both targets completed before any-return"
        pending = result["pending"]
        live = [self.binding(b["pane_id"]) for b in pending]
        assert all(o["state"] == "working" for o in live), live
        assert all(o["binding"] in pending for o in live), live
        # Observe natural completion without sending input or stopping the pending agent.
        follow = self.wait(
            result["next_input"]["targets"],
            after=result["next_input"]["after"],
            timeout=self.timeout,
        )
        assert any(
            e["kind"] == "settled" and e["binding"] in pending for e in follow["events"]
        ), follow
        for axis in axes:
            assert f"MULTI-{axis}-{self.run_id}" in self.read(
                self.bindings[axis]["pane_id"]
            ), "no attributable multi-target reply"
        return {"first": result, "still_working": live, "follow": follow}

    def working_settled(self, axis):
        pane = self.bindings[axis]["pane_id"]
        nonce = f"DONE-{axis}-{self.run_id}"
        self.herdr(
            "agent",
            "prompt",
            pane,
            "Do not use tools. Write integers 1 through 300 separated by spaces, "
            "then on a new line join these fragments with hyphens and no spaces: "
            f"DONE, {axis}, {self.run_id}.",
        )
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            target = self.target(axis)
            if target["baseline"]["state"] == "working":
                result = self.wait([target], timeout=min(45, self.timeout))
                if result["reason"] == "change":
                    assert any(e["kind"] == "settled" for e in result["events"]), result
                    assert nonce in self.read(pane), (
                        "wait returned without expected reply"
                    )
                    return result
                raise AssertionError(
                    "working target did not settle within wait deadline"
                )
            if target["baseline"]["state"] == "blocked":
                raise AssertionError("unexpected runtime dialog: " + self.read(pane))
            time.sleep(0.25)
        raise AssertionError(
            "no observed working phase; cannot certify a completed cycle"
        )

    def captain_return(self, axis):
        request = self.continuations[axis]
        dump(self.root / f"captain-input-{axis}.json", request)
        script = self.root / f"captain-wait-{axis}.py"
        evidence = self.root / f"captain-result-{axis}.json"
        script.write_text(
            "import json, os, pathlib, subprocess, sys\n"
            "d=subprocess.run(['herdr','status','--json'], capture_output=True, text=True)\n"
            f"r=subprocess.run({[*self.lb, 'agent', 'wait', '--input-file', f'captain-input-{axis}.json', '--timeout', '2', '--json']!r}, capture_output=True, text=True)\n"
            "e={'code':r.returncode,'stdout':r.stdout,'stderr':r.stderr,"
            "'herdr_status':{'code':d.returncode,'stdout':d.stdout,'stderr':d.stderr},"
            "'context':{k:os.environ.get(k) for k in "
            "['HERDR_ENV','HERDR_PANE_ID','HERDR_WORKSPACE_ID']}}\n"
            f"pathlib.Path({str(evidence)!r}).write_text(json.dumps(e,indent=2))\n"
            "print(r.stdout, end=''); print(r.stderr, file=sys.stderr, end='')\n"
            "sys.exit(r.returncode)\n"
        )
        receipt = self.root / f"captain-receipt-{axis}.txt"
        nonce = f"HOST-RETURN-{axis}-{self.run_id}"
        command = shlex.join([self.python, str(script)])
        prompt = (
            "You are the Captain for an authorized disposable integration test. "
            f"Run exactly this one foreground command: {command}\n"
            "The wait itself lasts two seconds. If the command tool supports "
            "yield_time_ms, set it to at least 10000 so it returns the completed "
            "foreground result rather than a running process/session identifier. "
            "Wait for the command's actual JSON result. After that tool call returns, "
            f"use a separate file-edit tool call to create {receipt.name} containing "
            "the actual reason followed by the hyphen-joined fragments "
            f"HOST-RETURN, {axis}, {self.run_id}. Do not combine the receipt write "
            "into the command, start background jobs, poll, prompt another agent, "
            "or change any other file. Then reply with the same nonce. "
            "This authorizes only the specified command and receipt in this test directory."
        )
        pane = self.bindings[axis]["pane_id"]
        self.herdr(
            "agent",
            "prompt",
            pane,
            prompt,
            "--wait",
            "--timeout",
            str(int(self.timeout * 1000)),
            timeout=self.timeout + 5,
        )
        reply = self.read(pane)
        if self.target(axis)["baseline"]["state"] == "blocked":
            raise Blocked("Captain tool permission dialog: " + reply[-2500:])
        assert receipt.exists() and evidence.exists(), (
            "Captain did not resume to write receipt: " + reply[-1500:]
        )
        text = receipt.read_text()
        observed = json.loads(evidence.read_text())
        actual = json.loads(observed["stdout"])
        assert nonce in text and actual["reason"] in text, text
        assert nonce in reply, "Captain completion not attributable"
        self.record(
            f"{axis}/captain-herdr-readiness",
            lambda: self.captain_readiness(actual, observed),
        )
        return {
            "receipt": text,
            "wait_reason": actual["reason"],
            "targets": request["targets"],
            "evidence_file": str(evidence.relative_to(self.output)),
            "reply_file": f"reply-{pane.replace(':', '-')}.txt",
            "limitation": "foreground tool return only; no detached wake claim",
        }

    def captain_readiness(self, actual, evidence):
        if actual["reason"] == "unavailable":
            raise Blocked("Captain cannot access Herdr: " + json.dumps(evidence))
        assert actual["reason"] == "timeout", actual
        return {"wait_reason": actual["reason"], "code": evidence["code"]}

    def close(self):
        failures = []
        for pane in reversed(self.owned):
            try:
                binding = next(
                    (
                        b
                        for b in {**self.cleanup_bindings, **self.bindings}.values()
                        if b["pane_id"] == pane
                    ),
                    None,
                )
                if binding:
                    dump(
                        self.root / "close.json",
                        {"binding": binding, "owned_panes": [pane]},
                    )
                    result = self.command(
                        [
                            *self.lb,
                            "agent",
                            "close-session",
                            "--input-file",
                            "close.json",
                            "--json",
                        ]
                    )
                    assert result["status"] == "closed", result
                else:
                    self.herdr("pane", "close", pane)
            except (AssertionError, OSError, subprocess.TimeoutExpired) as exc:
                failures.append({"pane": pane, "error": str(exc)})
        inventory = self.herdr(
            "pane", "list", "--workspace", os.environ["HERDR_WORKSPACE_ID"]
        )
        remaining = [
            p["pane_id"]
            for p in inventory["result"]["panes"]
            if p["pane_id"] in self.owned
        ]
        dump(
            self.output / "cleanup.json",
            {
                "failures": failures,
                "remaining": remaining,
                "descendant_process_cleanup": "not independently verified",
            },
        )
        assert not remaining and not failures, {
            "remaining": remaining,
            "failures": failures,
        }
        return {"owned_panes": self.owned, "remaining": remaining}

    def run(self):
        self.continuations = {}
        status = self.herdr("status", "--json")["server"]
        assert status.get("running") and status.get("compatible"), status
        self.server = status.get("session") or "default"
        self.original_panes = {
            p["pane_id"]
            for p in self.herdr(
                "pane", "list", "--workspace", os.environ["HERDR_WORKSPACE_ID"]
            )["result"]["panes"]
        }
        self.herdr("integration", "status")
        try:
            for axis, runtime in self.config["runtimes"].items():
                if (
                    self.record(
                        f"{axis}/acceptance-identity", lambda: self.start(axis, runtime)
                    )
                    and "core" in self.cases
                ):
                    self.record(
                        f"{axis}/snapshot-timeout-readonly",
                        lambda: self.snapshots(axis),
                    )
                    self.record(
                        f"{axis}/invalid-token-identity", lambda: self.invalid(axis)
                    )
                    if axis in self.continuations:
                        self.record(
                            f"{axis}/interruption", lambda: self.interrupted(axis)
                        )
                    self.record(
                        f"{axis}/working-settled", lambda: self.working_settled(axis)
                    )
            if len(self.bindings) >= 2 and "multi" in self.cases:
                self.record("multi-target/real-observations", self.multi)
                self.record("multi-target/any-return-while-working", self.multi_active)
            for axis in self.bindings if "captain" in self.cases else ():
                self.record(
                    f"{axis}/captain-foreground-return",
                    lambda: self.captain_probe(axis),
                )
        finally:
            self.record("owned-resource-cleanup", self.close)
        return 0 if all(c["status"] == "PASS" for c in self.checks) else 1

    def captain_probe(self, axis):
        # Captain observes distinct Sailors, never its own tool-running lifecycle.
        targets = [self.target(other) for other in self.bindings if other != axis]
        assert targets, "Captain probe requires a distinct accepted Sailor"
        first = self.wait(targets, timeout=2)
        self.continuations[axis] = first["next_input"]
        return self.captain_return(axis)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-live", action="store_true", required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--cases",
        nargs="+",
        choices=("core", "multi", "captain"),
        default=("core", "multi", "captain"),
        help="case groups; acceptance and owned-resource cleanup always run",
    )
    args = parser.parse_args()
    if os.environ.get("HERDR_ENV") != "1" or not all(
        os.environ.get(k) for k in ("HERDR_PANE_ID", "HERDR_WORKSPACE_ID")
    ):
        parser.error("run only from a Herdr-managed caller with native context")
    if not shutil.which("herdr"):
        parser.error("herdr is unavailable")
    try:
        config = load_config(args.config)
        output = args.output.resolve()
        output.mkdir(parents=True, exist_ok=False)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    sys.path.insert(0, str(REPO / "src"))
    from logbook_cli.document import LbError

    suite = LiveSuite(config, output, args.cases)
    try:
        return suite.run()
    except (
        AssertionError,
        ValueError,
        KeyError,
        TypeError,
        LbError,
        OSError,
        subprocess.TimeoutExpired,
    ) as exc:
        dump(output / "runner-error.json", {"error": str(exc)})
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
