"""Evidence provenance, delegation policy, and real failure/recovery boundaries."""

import copy
import json
import shlex
import unittest
from unittest.mock import patch

import test_domain_commands as fixtures

from logbook_cli import execution
from logbook_cli.cli import app
from logbook_cli.document import LbError
from logbook_cli.services.common import load


def source(kind="runtime_observation", ref="runtime observation 1"):
    return {"kind": kind, "ref": ref}


def takeover():
    return dict(
        id="takeover-1",
        kind="takeover",
        source=source("human_instruction", "existing user message 2"),
        origin="explicit",
        release_condition=None,
    )


def ownership(identity="owner-1", owner="captain", conflicts=False, settled=True):
    return dict(
        id=identity,
        kind="ownership",
        source=source(),
        takeover_id="takeover-1",
        owner=owner,
        conflicts=conflicts,
        settled=settled,
    )


def release(scope="dispatch"):
    return dict(
        id="release-1",
        kind="delegation-release",
        source=source("human_instruction", "existing user message 4"),
        takeover_id="takeover-1",
        dispatch_id="d1",
        recipient="tester",
        scope=scope,
        condition_result_id=None,
    )


def handoff(identity="handoff-1", **statuses):
    values = {
        "receipt": "accepted",
        "execution_ready": "ready",
        "monitor_ready": "ready",
        "ownership": "recipient",
    }
    values.update(statuses)
    return dict(
        id=identity,
        kind="handoff",
        release_id="release-1",
        **{
            key: {"status": value, "source": source(ref=key + " observation")}
            for key, value in values.items()
        },
    )


class ExecutionTest(unittest.TestCase):
    setUp = fixtures.DomainTest.setUp
    token = fixtures.DomainTest.token
    state = fixtures.DomainTest.state
    json_file = fixtures.DomainTest.json_file
    identify = fixtures.DomainTest.identify
    transition = fixtures.DomainTest.transition
    dispatch_call = fixtures.DomainTest.dispatch_call

    def call(self, *args, code=0):
        result = fixtures.DomainTest.call(self, *args, code=code)
        if code:
            self.assertIsInstance(result.exception, LbError)
            self.assertEqual(result.exception.code, code)
        return result

    def context(self):
        return self.call("log", "execution", "context", "log.md")

    def record(self, *facts, code=0, dry=False, token=None):
        payload = {"facts": list(facts)}
        if self.context()["state"] is None:
            payload.update(
                name="demo", thinking="thinking.md", advancement="authorized-round"
            )
        self.json_file("facts.json", payload)
        return self.call(
            "log",
            "execution",
            "record",
            "log.md",
            "--input-file",
            "facts.json",
            "--expect-version",
            token or self.context()["version_token"],
            *(["--dry-run"] if dry else []),
            code=code,
        )

    def prepare(self):
        self.state("active")
        self.identify()
        self.dispatch_input()

    def dispatch_input(self, identity="d1", owner="tester", task="build"):
        return self.json_file(
            "dispatch.json",
            dict(
                id=identity,
                task_id=task,
                owner=owner,
                scope="review",
                exclusions="publication",
                inputs="candidate-a",
                completion="independent review",
                escalation="blocked",
            ),
        )

    def setup_send(self, scope="dispatch"):
        self.prepare()
        self.record(takeover(), ownership(), release(scope))
        self.dispatch_call("create", "--input-file", "dispatch.json")
        self.json_file(
            "binding.json",
            dict(
                machine="local",
                workspace_id="w1",
                tab_id="w1:t1",
                pane_id="w1:p1",
                agent_id="tester",
                session_id="s1",
                observed_at="2026-01-01T00:00:00Z",
                basis="saved binding, not proof",
            ),
        )
        self.call(
            "agent",
            "bind",
            "log.md",
            "--thinking",
            "thinking.md",
            "d1",
            "--input-file",
            "binding.json",
            "--expect-version",
            self.token("thinking.md"),
        )
        (self.root / "message.txt").write_text("Review candidate-a only")
        observation = {
            "live_verified": True,
            "observation_token": "o1",
            "observation": {"state": "idle"},
        }
        self.observer = patch(
            "logbook_cli.adapters.herdr.inspect", return_value=observation
        ).start()
        self.addCleanup(patch.stopall)
        self.transport = patch(
            "logbook_cli.adapters.herdr.invoke",
            return_value={"accepted": True, "receipt_id": "r1"},
        ).start()

    def send(self, identity="op1", code=0, dry=False, token=None):
        return self.call(
            "agent",
            "send",
            "log.md",
            "d1",
            "--thinking",
            "thinking.md",
            "--message-file",
            "message.txt",
            "--operation-id",
            identity,
            "--expected-session",
            "s1",
            "--expected-observation",
            "o1",
            "--expect-version",
            self.token("thinking.md"),
            "--expect-execution-version",
            token or self.context()["version_token"],
            *(["--dry-run"] if dry else []),
            code=code,
        )

    def resolution(self, outcome):
        return dict(
            id="resolve-1",
            kind="transport-resolution",
            source=source(ref="runtime delivery lookup for op1"),
            operation_id="op1",
            outcome=outcome,
        )

    def test_wrong_document_token_identifies_thinking_and_recovers_without_reapproval(self):
        self.prepare()
        self.record(takeover(), ownership(), release())
        before = (self.root / "thinking.md").read_bytes()
        result = self.call(
            "dispatch", "create", "log.md", "--thinking", "thinking.md",
            "--input-file", "dispatch.json", "--expect-version", self.token(), code=4,
        )
        message = str(result.exception)
        self.assertIn("version token differs for thinking.md", message)
        command = shlex.split(message.split("`")[1])
        self.assertEqual(command[-4:], ["log", "context", "thinking.md", "--json"])
        self.assertEqual((self.root / "thinking.md").read_bytes(), before)
        context = self.runner.invoke(app, command[1:])
        token = json.loads(context.output)["version_token"]
        self.call(
            "dispatch", "create", "log.md", "--thinking", "thinking.md",
            "--input-file", "dispatch.json", "--expect-version", token,
        )
        self.assertEqual(len(self.context()["state"]["facts"]), 3)

    def test_wrong_execution_token_recovery_command_and_send_have_no_effect(self):
        self.setup_send()
        before = (self.root / "lb/demo.json").read_bytes()
        result = self.send(token=self.token("thinking.md"), code=4)
        message = str(result.exception)
        self.assertIn("execution version token differs for lb/demo.json", message)
        command = shlex.split(message.split("`")[1])
        self.assertEqual(command[-5:], ["log", "execution", "context", "log.md", "--json"])
        self.assertEqual((self.root / "lb/demo.json").read_bytes(), before)
        self.transport.assert_not_called()
        context = self.runner.invoke(app, command[1:])
        self.send(token=json.loads(context.output)["version_token"])
        self.assertEqual(self.transport.call_count, 1)

    def test_outside_input_error_preserves_state_and_explains_root(self):
        import tempfile
        from pathlib import Path

        self.record(takeover(), ownership())
        before = (self.root / "lb/demo.json").read_bytes()
        with tempfile.TemporaryDirectory() as outside:
            path = Path(outside) / "facts.json"
            path.write_text(json.dumps({"facts": [release()]}))
            result = self.call(
                "log", "execution", "record", "log.md", "--input-file", str(path),
                "--expect-version", self.context()["version_token"], code=3,
            )
        self.assertIn("save the authorized input inside this root", str(result.exception))
        self.assertIn(str(self.root), str(result.exception))
        self.assertEqual((self.root / "lb/demo.json").read_bytes(), before)
        self.record(release())

    def test_public_commands_describe_effects_not_internal_phases(self):
        commands = app.commands["log"].commands["execution"].commands
        self.assertEqual(set(commands), {"context", "record"})
        self.assertNotIn(
            "--basis",
            {
                opt
                for param in app.commands["agent"].commands["send"].params
                for opt in getattr(param, "opts", [])
            },
        )
        self.assertNotIn(
            "--basis",
            {
                opt
                for param in commands["record"].params
                for opt in getattr(param, "opts", [])
            },
        )

    def test_already_owned_batch_is_idempotent_without_session_metadata(self):
        before = (self.log.read_bytes(), self.thinking.read_bytes())
        with patch("logbook_cli.adapters.herdr.control") as runtime:
            result = self.record(takeover(), ownership())
            saved = (self.root / "lb/demo.json").read_bytes()
            again = self.record(takeover(), ownership())
            runtime.assert_not_called()
        self.assertTrue(result["record_saved"])
        self.assertFalse(result["runtime_transfer_verified"])
        self.assertIn("caller-reported", result["fact_assurance"])
        self.assertEqual(result["projection"]["reported_owner"], "captain")
        self.assertFalse(again["changed"])
        self.assertEqual(saved, (self.root / "lb/demo.json").read_bytes())
        self.assertEqual(before, (self.log.read_bytes(), self.thinking.read_bytes()))

    def test_basis_or_caller_judgment_cannot_certify_ownership(self):
        claim = ownership()
        claim["source"] = source("caller_judgment", "I think pause succeeded")
        self.record(takeover(), claim)
        self.assertEqual(self.context()["projection"]["reported_owner"], "unknown")
        self.assertEqual(self.context()["reply_prefix"], "")
        forged = ownership("forged")
        forged["verified"] = True
        self.record(forged, code=4)

    def test_pause_failure_keeps_restriction_and_never_calls_runtime(self):
        self.prepare()
        with patch("logbook_cli.adapters.herdr.control") as runtime:
            self.record(
                takeover(), ownership(owner="sailor", conflicts=True, settled=False)
            )
            self.dispatch_call("create", "--input-file", "dispatch.json", code=4)
            runtime.assert_not_called()
        self.assertTrue(self.context()["delegation_restricted"])
        self.assertEqual(self.context()["reply_prefix"], "")

    def test_completion_and_restart_do_not_authorize_next_review(self):
        self.prepare()
        self.record(takeover(), ownership())
        self.transition("start")
        self.json_file(
            "result.json", {"candidate": "a", "evidence": ["Captain self-tests"]}
        )
        self.transition("record-result", "--input-file", "result.json")
        self.transition("accept", "--candidate", "a")
        self.log.write_text(self.log.read_text() + "- [ ] Independent review @tester\n")
        self.identify("Independent review @tester", "review")
        self.dispatch_input(task="review")
        result = self.dispatch_call("create", "--input-file", "dispatch.json", code=4)
        self.assertIn("keep independent review pending", str(result.exception))
        self.assertEqual(self.context()["projection"]["takeover"]["id"], "takeover-1")
        self.assertIn("- [ ] Independent review", self.log.read_text())

    def test_bounded_release_uses_existing_permission_and_preserves_others(self):
        self.prepare()
        self.record(takeover(), ownership(), release())
        self.dispatch_call("create", "--input-file", "dispatch.json")
        self.record(handoff())
        self.assertTrue(self.context()["projection"]["handoff_reported_complete"])
        self.assertFalse(self.context()["runtime_transfer_verified"])
        self.assertTrue(self.context()["delegation_restricted"])
        self.dispatch_input("d2")
        self.dispatch_call("create", "--input-file", "dispatch.json", code=4)
        self.assertFalse(self.record(release(), handoff())["changed"])

    def test_receipt_readiness_and_ownership_are_distinct(self):
        self.record(takeover(), ownership(), release("advancement"))
        for index, patches in enumerate(
            [
                {"monitor_ready": "unknown"},
                {"execution_ready": "not_ready"},
                {"ownership": "captain"},
                {"receipt": "unknown"},
            ]
        ):
            self.record(handoff(f"h{index}", **patches))
            self.assertFalse(self.context()["projection"]["handoff_reported_complete"])
            self.assertTrue(self.context()["delegation_restricted"])
        self.record(handoff("complete"))
        self.assertFalse(self.context()["delegation_restricted"])
        self.assertEqual(self.context()["reply_prefix"], "")
        self.assertFalse(self.context()["runtime_transfer_verified"])

    def test_pre_authorized_condition_requires_matching_result_and_bound(self):
        request = takeover()
        request["release_condition"] = {
            "id": "checks-pass",
            "source": source("human_instruction", "existing conditional instruction"),
            "dispatch_id": "d1",
            "recipient": "tester",
            "scope": "dispatch",
        }
        self.record(request, ownership())
        grant = release()
        grant.update(
            source=source("caller_judgment", "condition is satisfied"),
            condition_result_id="check1",
        )
        self.record(grant, code=4)
        check = dict(
            id="check1",
            kind="condition-result",
            source={
                "kind": "verified_result",
                "ref": "test report",
                "verifier": "local checks",
                "subject": "candidate-a",
            },
            takeover_id="takeover-1",
            condition_id="checks-pass",
            satisfied=True,
        )
        self.record(check)
        broad = copy.deepcopy(grant)
        broad["scope"] = "advancement"
        self.record(broad, code=4)
        self.record(grant)
        self.assertFalse(self.record(grant)["changed"])

    def test_dry_run_and_stale_json_token(self):
        absent = self.context()["version_token"]
        self.record(takeover(), dry=True)
        self.assertFalse((self.root / "lb").exists())
        self.record(takeover())
        before = (self.root / "lb/demo.json").read_bytes()
        self.record(ownership(), token=absent, code=4)
        self.assertEqual(before, (self.root / "lb/demo.json").read_bytes())

    def test_changed_fact_id_is_refused(self):
        self.record(takeover(), ownership())
        self.record(ownership(conflicts=True), code=4)
        self.assertEqual(self.context()["projection"]["reported_owner"], "captain")

    def test_json_markdown_disagreement_is_repaired_without_state_transition(self):
        self.state("active")
        self.record(takeover(), ownership())
        self.assertFalse(self.context()["page_projection_matches"])
        saved = (self.root / "lb/demo.json").read_bytes()
        old = self.token()
        self.log.write_text(self.log.read_text() + "\nHuman note\n")
        self.call("log", "sync", "log.md", "--expect-version", old, code=4)
        self.assertEqual(saved, (self.root / "lb/demo.json").read_bytes())
        for _ in range(2):
            self.call("log", "sync", "log.md", "--expect-version", self.token())
        self.assertTrue(self.context()["page_projection_matches"])
        self.assertIn("Human note", self.log.read_text())
        self.record(release("advancement"), handoff())
        self.assertFalse(self.context()["page_projection_matches"])
        self.assertFalse(self.context()["delegation_restricted"])
        self.call("log", "sync", "log.md", "--expect-version", self.token())
        self.assertTrue(self.context()["page_projection_matches"])

    def test_send_saves_intent_before_effect_and_replays_without_resending(self):
        self.setup_send()

        def invoke(*args, **kwargs):
            durable = self.context()["state"]["operations"]
            self.assertEqual(durable[0]["outcome"], "unknown")
            return {"receipt_id": "r1"}

        self.transport.side_effect = invoke
        first = self.send()
        self.assertEqual(first["operation"]["outcome"], "submitted")
        self.assertEqual(self.transport.call_count, 1)
        self.assertTrue(self.send()["replayed_record"])
        self.assertEqual(self.transport.call_count, 1)
        (self.root / "message.txt").write_text("different package")
        self.send(code=4)
        self.assertEqual(self.transport.call_count, 1)

    def test_failed_live_precondition_never_creates_send_intent(self):
        self.setup_send()
        self.observer.return_value["live_verified"] = False
        self.send(code=4)
        self.assertEqual(self.context()["state"]["operations"], [])
        self.transport.assert_not_called()

    def test_send_preview_has_no_journal_or_transport_effect(self):
        self.setup_send()
        before = (self.root / "lb/demo.json").read_bytes()
        self.send(dry=True)
        self.transport.assert_not_called()
        self.assertEqual(before, (self.root / "lb/demo.json").read_bytes())

    def test_unknown_send_cannot_be_overridden_by_new_id_or_handoff_report(self):
        self.setup_send("advancement")
        self.transport.side_effect = LbError("transport timeout; outcome unknown", 4)
        self.send(code=4)
        self.assertEqual(self.context()["state"]["operations"][0]["outcome"], "unknown")
        self.send(code=4)
        self.send("op2", code=4)
        self.record(handoff())
        self.assertTrue(self.context()["delegation_restricted"])
        self.assertFalse(self.context()["projection"]["handoff_reported_complete"])
        self.assertEqual(self.transport.call_count, 1)

    def test_reconcile_non_delivery_allows_one_new_attempt_without_reauthorization(
        self,
    ):
        self.setup_send()
        self.transport.side_effect = LbError("timeout", 4)
        self.send(code=4)
        self.record(self.resolution("not_submitted"))
        self.transport.side_effect = None
        self.send("op2")
        self.assertEqual(self.transport.call_count, 2)
        self.assertEqual(
            sum(
                f["kind"] == "delegation-release"
                for f in self.context()["state"]["facts"]
            ),
            1,
        )

    def test_reconcile_delivered_never_resends(self):
        self.setup_send()
        self.transport.side_effect = LbError("timeout", 4)
        self.send(code=4)
        self.record(self.resolution("submitted"))
        self.assertTrue(self.send()["replayed_record"])
        self.send("op2", code=4)
        self.assertEqual(self.transport.call_count, 1)

    def test_crash_after_intent_survives_process_recovery(self):
        self.setup_send()
        self.transport.side_effect = KeyboardInterrupt()
        result = self.runner.invoke(
            app,
            [
                "--root",
                str(self.root),
                "agent",
                "send",
                "log.md",
                "d1",
                "--thinking",
                "thinking.md",
                "--message-file",
                "message.txt",
                "--operation-id",
                "op1",
                "--expected-session",
                "s1",
                "--expected-observation",
                "o1",
                "--expect-version",
                self.token("thinking.md"),
                "--expect-execution-version",
                self.context()["version_token"],
                "--json",
            ],
        )
        self.assertNotEqual(result.exit_code, 0)
        self.assertEqual(self.context()["state"]["operations"][0]["outcome"], "unknown")
        self.transport.side_effect = None
        self.send("op2", code=4)
        self.assertEqual(self.transport.call_count, 1)

    def test_intent_write_failure_prevents_transport(self):
        self.setup_send()
        with patch(
            "logbook_cli.execution.write", side_effect=LbError("CAS changed", 4)
        ):
            self.send(code=4)
        self.transport.assert_not_called()
        self.assertEqual(self.context()["state"]["operations"], [])

    def test_receipt_write_failure_returns_actual_receipt_and_keeps_unknown(self):
        self.setup_send()
        original = execution.write
        calls = []

        def save(*args, **kwargs):
            calls.append(1)
            if len(calls) == 2:
                raise OSError("disk full")
            return original(*args, **kwargs)

        with patch("logbook_cli.execution.write", side_effect=save):
            result = self.runner.invoke(
                app,
                [
                    "--root",
                    str(self.root),
                    "agent",
                    "send",
                    "log.md",
                    "d1",
                    "--thinking",
                    "thinking.md",
                    "--message-file",
                    "message.txt",
                    "--operation-id",
                    "op1",
                    "--expected-session",
                    "s1",
                    "--expected-observation",
                    "o1",
                    "--expect-version",
                    self.token("thinking.md"),
                    "--expect-execution-version",
                    self.context()["version_token"],
                    "--json",
                ],
            )
        self.assertEqual(result.exit_code, 4)
        output = json.loads(result.output)
        self.assertEqual(output["transport_outcome"], "submitted")
        self.assertFalse(output["record_saved"])
        self.assertEqual(self.context()["state"]["operations"][0]["outcome"], "unknown")
        self.send("op2", code=4)
        self.assertEqual(self.transport.call_count, 1)

    def test_simultaneous_writer_cannot_send_or_append_another_fact(self):
        self.setup_send()
        with execution.writer(load(str(self.root), "log.md")):
            self.send(code=4)
            self.record(ownership("owner-2"), code=4)
        self.transport.assert_not_called()

    def test_alternate_thinking_cannot_bypass_gate(self):
        self.prepare()
        self.record(takeover(), ownership(), release())
        (self.root / "other.md").write_text("# Other\n")
        self.call(
            "dispatch",
            "create",
            "log.md",
            "--thinking",
            "other.md",
            "--input-file",
            "dispatch.json",
            "--expect-version",
            self.token("other.md"),
            code=4,
        )

    def test_corrupt_or_duplicate_json_and_symlink_fail_closed(self):
        self.record(takeover())
        path = self.root / "lb/demo.json"
        saved = path.read_bytes()
        for bad in ["{broken", '{"name":"a","name":"b"}']:
            path.write_text(bad)
            self.call("log", "execution", "context", "log.md", code=4)
        path.write_bytes(saved)
        duplicate = json.loads(saved)
        duplicate["name"] = "other"
        self.json_file("lb/other.json", duplicate)
        self.call("log", "execution", "context", "log.md", code=4)
        (self.root / "lb/other.json").unlink()
        path.unlink()
        path.symlink_to(self.thinking)
        self.call("log", "execution", "context", "log.md", code=4)

    def test_other_records_and_unrelated_json_do_not_block_this_logbook(self):
        self.record(takeover())
        other = json.loads((self.root / "lb/demo.json").read_bytes())
        other.update(name="other", log="gone.md", facts=[{"kind": "bogus"}])
        self.json_file("lb/other.json", other)
        self.json_file("lb/unrelated.json", {"foo": 1})
        self.assertTrue(self.context()["delegation_restricted"])
        self.call("log", "context", "log.md")
        (self.root / "lb/unrelated.json").write_text("{broken")
        result = self.call("log", "execution", "context", "log.md", code=4)
        self.assertIn("unrelated.json", str(result.exception))
        (self.root / "lb/unrelated.json").unlink()
        broken = json.loads((self.root / "lb/demo.json").read_bytes())
        broken["facts"] = [{"kind": "bogus"}]
        (self.root / "lb/demo.json").write_text(json.dumps(broken))
        result = self.call("log", "execution", "context", "log.md", code=4)
        self.assertIn("demo.json", str(result.exception))

    def test_send_creates_empty_record_and_record_defaults_match_it(self):
        self.setup_send()
        (self.root / "lb/demo.json").unlink()
        self.send()
        state = json.loads((self.root / "lb/log.json").read_text())
        self.assertEqual(
            (state["name"], state["advancement"], state["thinking"], state["facts"]),
            ("log", "log", "thinking.md", []),
        )
        self.assertEqual(state["operations"][0]["outcome"], "submitted")
        self.assertFalse(self.context()["delegation_restricted"])
        self.json_file("facts.json", {"thinking": "thinking.md", "facts": []})
        self.call(
            "log", "execution", "record", "log.md", "--input-file", "facts.json",
            "--expect-version", self.context()["version_token"],
        )

    def test_project_binding_and_optional_captain_label(self):
        project = self.root / "projects/example"
        (project / "docs").mkdir(parents=True)
        (project / "mind.yaml").write_text('schema: "1"\n')
        (project / "docs/log.md").write_bytes(self.log.read_bytes())
        (project / "thinking.md").write_bytes(self.thinking.read_bytes())
        log = "projects/example/docs/log.md"
        self.json_file(
            "facts.json",
            dict(
                name="stable",
                thinking="projects/example/thinking.md",
                advancement="round",
                facts=[takeover(), ownership()],
            ),
        )
        self.call(
            "log",
            "execution",
            "record",
            log,
            "--input-file",
            "facts.json",
            "--expect-version",
            self.call("log", "execution", "context", log)["version_token"],
        )
        state = json.loads((project / "lb/stable.json").read_text())
        self.assertEqual(state["log"], "docs/log.md")
        self.assertEqual(state["captain"], "captain")
        self.assertFalse((self.root / "lb").exists())

    def test_invalid_batch_does_not_partially_record_permission(self):
        self.record(takeover(), ownership())
        before = (self.root / "lb/demo.json").read_bytes()
        invalid = handoff()
        invalid["release_id"] = "missing"
        self.record(release(), invalid, code=4)
        self.assertEqual(before, (self.root / "lb/demo.json").read_bytes())

    def test_automatic_exit_cannot_override_explicit_takeover(self):
        self.record(takeover(), ownership())
        automatic = takeover()
        automatic.update(
            id="auto",
            origin="automatic",
            source=source("caller_judgment", "hard problem"),
        )
        self.record(automatic, code=4)
        self.assertEqual(self.context()["projection"]["takeover"]["id"], "takeover-1")

    def test_automatic_exit_uses_existing_bounded_authority(self):
        automatic = takeover()
        automatic.update(
            origin="automatic",
            source=source(
                "caller_judgment", "direct reasoning under existing execution authority"
            ),
            release_condition={
                "id": "exit",
                "source": source("caller_judgment", "repair and self-test"),
                "dispatch_id": "d1",
                "recipient": "tester",
                "scope": "dispatch",
            },
        )
        self.record(automatic, ownership())
        check = dict(
            id="check1",
            kind="condition-result",
            source={
                "kind": "verified_result",
                "ref": "self-test output",
                "verifier": "local checker",
                "subject": "candidate-a",
            },
            takeover_id="takeover-1",
            condition_id="exit",
            satisfied=True,
        )
        grant = release()
        grant.update(
            source=source("caller_judgment", "existing automatic return authority"),
            condition_result_id="check1",
        )
        self.record(check, grant)
        self.assertEqual(self.context()["projection"]["release"]["scope"], "dispatch")

    def test_new_conflicting_observation_revokes_reported_completion(self):
        self.record(takeover(), ownership(), release("advancement"), handoff())
        self.assertFalse(self.context()["delegation_restricted"])
        self.record(ownership("conflict-now", conflicts=True))
        self.assertTrue(self.context()["delegation_restricted"])
        self.assertEqual(self.context()["projection"]["reported_owner"], "unknown")

    def test_saved_send_receipt_can_be_read_after_lifecycle_pause(self):
        self.setup_send()
        self.send()
        self.state("paused")
        self.assertTrue(self.send()["replayed_record"])
        self.assertEqual(self.transport.call_count, 1)

    def test_legacy_marker_blocks_delegation_without_json(self):
        self.prepare()
        self.log.write_text(
            self.log.read_text().replace(
                "- [ ] Build @core\n",
                "- [ ] Build @core\n    - 状态：👨‍✈️ Captain takeover\n",
            )
        )
        self.dispatch_call("create", "--input-file", "dispatch.json", code=4)

    def test_same_operation_id_cannot_be_replayed_for_another_runtime_target(self):
        self.setup_send()
        self.send()
        binding = json.loads((self.root / "binding.json").read_text())
        binding["pane_id"] = "w1:p2"
        self.json_file("binding.json", binding)
        self.call(
            "agent",
            "bind",
            "log.md",
            "--thinking",
            "thinking.md",
            "d1",
            "--input-file",
            "binding.json",
            "--expect-version",
            self.token("thinking.md"),
        )
        self.send(code=4)
        self.assertEqual(self.transport.call_count, 1)
