import hashlib
import json
import unittest
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from logbook_cli import bootstrap, execution, execution_facts, unified
from logbook_cli.adapters import herdr
from logbook_cli.bootstrap import CliIdentity
from logbook_cli.document import LbError, parse_text
from logbook_cli.services import self_check
from logbook_cli.services.readiness import unresolved_operation
from logbook_cli.services.self_check import _live, check_recipient
from logbook_cli.services.task_coordination import recipient_launcher_version
from logbook_cli.services.transport import send, send_task, task_send_guard


class TaskTransportTests(unittest.TestCase):
    def test_passed_self_check_does_not_clear_other_required_checks(self):
        root = Path("/example")
        doc = parse_text(b"# Work\n", root / "log.md", root)
        recipient = self_check.Recipient({"session_id": "native"}, root, "environment")
        plan = {
            "scope_ref": "scope",
            "candidate_ref": "candidate",
            "source": "approved",
            "checks": [
                {"check_id": "build", "subject_id": "dev"},
                {"check_id": "quality", "subject_id": "qa"},
            ],
        }
        for evidence in (None, Mock(status="failed", source="current reply")):
            with (
                self.subTest(evidence=evidence),
                patch.object(self_check, "check_recipient", return_value=recipient),
                patch.object(self_check, "Cache") as cache,
                patch.object(self_check, "_live"),
            ):
                cache.return_value.get.side_effect = [Mock(status="passed"), evidence]
                gap = Mock()
                self_check.verify(doc, {"identity": {"run_id": "run"}}, "work", plan, gap)
                gap.assert_called_once()
                self.assertEqual(gap.call_args.args[2]["owner"], "qa")

    def test_preparation_reply_waits_for_durable_transport_resolution(self):
        root = Path("/example")
        doc = parse_text(b"# Work\n", root / "log.md", root)
        recipient = self_check.Recipient({"session_id": "native"}, root, "environment")
        plan = {"scope_ref": "scope", "candidate_ref": "candidate", "source": "approved"}
        check = {"check_id": "build", "subject_id": "worker"}
        op = {"outcome": "unknown", "request": {
            "action": "self-check", "run_id": "a" * 32, "task_id": "work", "check_id": "build",
            "plan_digest": unified.digest(plan), "binding_digest": recipient.digest,
            "session_id": "native", "correlation": "correlation", "message_digest": "prompt",
            "intent_at": "2026-01-01T00:00:00Z",
        }}
        run = {"execution": {"operations": {"check-op": op}}}
        reply = Mock(status="passed", digest="authentic-reply", evidence="build inputs present",
                     observed_at=datetime.now(timezone.utc).isoformat())
        with (
            patch.object(self_check, "load", return_value=doc),
            patch.object(self_check, "_input", return_value={"operation_id": "check-op"}),
            patch.object(self_check, "_planned", return_value=(plan, check, recipient)),
            patch.object(self_check.unified, "locate", return_value=(None, run)),
            patch.object(self_check, "_live"),
            patch.object(self_check.codex_replies, "read_reply", return_value=reply),
            patch.object(self_check, "Cache") as cache,
        ):
            with self.assertRaisesRegex(LbError, "reconcile the original preparation operation"):
                self_check.collect(root, "log.md", "observe.json")
            cache.assert_not_called()
            op["outcome"] = "submitted"
            result = self_check.collect(root, "log.md", "observe.json")
            self.assertEqual(result.value["status"], "passed")
            self.assertEqual(result.value["evidence"], "build inputs present")
            self.assertEqual(result.value["subject_id"], "worker")
            actual = cache.return_value.record.call_args.args[0]
            self.assertEqual(actual.response_ref, "check-op")
            self.assertEqual(actual.source, "authentic-reply")

    def test_unanswered_submitted_self_check_can_be_retried_after_expiry(self):
        sent = datetime(2026, 1, 1, tzinfo=timezone.utc)
        request = {"task_id": "work", "session_id": "native"}
        operations = {"check": {"outcome": "submitted", "request": {
            **request, "intent_at": sent.isoformat(),
            "correlation": "correlation", "message_digest": "prompt",
        }}}
        path = Path("/example")
        with patch.object(self_check.codex_replies, "read_reply", return_value=None) as read:
            with self.assertRaisesRegex(LbError, "original submitted self-check"):
                self_check._require_no_pending_reply(operations, request, path, sent)
            read.assert_called_once_with("native", path, "correlation", "prompt", sent)
            read.reset_mock()
            self_check._require_no_pending_reply(
                operations, request, path, sent + timedelta(minutes=30)
            )
            read.assert_not_called()

    def test_approved_preparation_environment_is_stable_until_identity_changes(self):
        native = {
            "machine": "local", "server": "default", "session_id": "native",
            "workspace_id": "w1", "tab_id": "w1:t1", "pane_id": "w1:p1", "agent_id": "codex",
        }
        check = {"check_id": "build", "subject_id": "worker", "environment": {
            "binding": native, "working_directory": "/example",
        }}
        tasks = {}
        run = {"execution": {"tasks": tasks}}
        recipient = check_recipient(run, "work", check)
        with (
            patch.object(herdr, "resolve_binding_scope", return_value=(native, None)),
            patch.object(herdr, "inspect", return_value={
                "observation": {"cwd": "/different"}, "live_verified": True,
            }),
        ):
            with self.assertRaisesRegex(LbError, "working directory|work directory"):
                _live(recipient)
        binding = {
            "machine": "local", "session_id": "native", "subject": {"kind": "agent", "subject_id": "worker"},
            "runtime_locator": {key: native[key] for key in ("server", "workspace_id", "tab_id", "pane_id", "agent_id")},
            "work_context": {"working_directory": "/example"},
            "observed_at": "2026-01-01T00:00:00Z", "basis": "reviewed assignment",
        }
        tasks["work"] = {"execution_bindings": {"current": binding}, "current_binding_id": "current"}
        self.assertEqual(check_recipient(run, "work", check), recipient)
        binding["session_id"] = "replacement"
        with self.assertRaisesRegex(LbError, "approved preparation environment"):
            check_recipient(run, "work", check)

    def test_preparation_receipt_is_not_a_business_action(self):
        op = {
            "outcome": "submitted",
            "request": {"task_id": "work", "action": "self-check"},
        }
        ex = {"operations": {"prepare": op}, "facts": []}
        request = {"task_id": "work", "binding_id": "binding"}
        self.assertFalse(unresolved_operation(ex, "work"))
        self.assertIsNone(task_send_guard(ex, "work", "delivery", request))
        op["outcome"] = "unknown"
        self.assertTrue(unresolved_operation(ex, "work"))
        with self.assertRaisesRegex(LbError, "unknown delivery"):
            task_send_guard(ex, "work", "delivery", request)

    def test_captain_start_requires_a_task_release_before_recipient_send(self):
        ex = {"operations": {"captain": {
            "provenance": "takeover", "outcome": "submitted",
            "request": {"task_id": "work"},
        }}}
        request = {"task_id": "work", "binding_id": "binding"}
        with self.assertRaisesRegex(LbError, "Captain already started"):
            task_send_guard(ex, "work", "new-op", request)
        self.assertIsNone(task_send_guard(ex, "work", "new-op", request, released=True))

    def test_task_release_does_not_alias_dispatch_with_same_id(self):
        source = {"kind": "human_instruction", "ref": "approved work"}
        takeover = {"id": "takeover", "kind": "takeover", "source": source,
                    "origin": "explicit", "release_condition": None}
        release = {"id": "release", "kind": "delegation-release", "source": source,
                   "takeover_id": "takeover", "recipient": "sailor",
                   "condition_result_id": None}
        task = {**release, "scope": "task", "task_id": "work"}
        dispatch = {**release, "scope": "dispatch", "dispatch_id": "work"}
        for fact in (task, dispatch):
            execution_facts.validate_fact(fact, [takeover])
        value = {"facts": [takeover, task], "operations": [], "captain": "captain"}
        with patch.object(execution, "read", return_value=(None, b"", value)):
            self.assertEqual(execution.require_delegation(None, owner="sailor", task_id="work"), task)
            with self.assertRaises(LbError):
                execution.require_delegation(None, "work", "sailor")
            value["facts"][-1] = dispatch
            self.assertEqual(execution.require_delegation(None, "work", "sailor"), dispatch)
            with self.assertRaises(LbError):
                execution.require_delegation(None, owner="sailor", task_id="work")

    def test_task_handoff_projection_rechecks_effective_send_and_binding(self):
        source = {"kind": "runtime_observation", "ref": "verified live"}
        takeover = {"id": "takeover", "kind": "takeover"}
        owner = {"id": "owner", "kind": "ownership", "source": source, "owner": "captain",
                 "settled": True, "conflicts": False}
        release = {"id": "release", "kind": "delegation-release", "scope": "task",
                   "task_id": "work", "recipient": "sailor"}
        handoff = {
            "id": "handoff", "kind": "handoff", "release_id": "release",
            "operation_id": "send",
            "receipt": {"status": "accepted", "source": source},
            "execution_ready": {"status": "ready", "source": source},
            "monitor_ready": {"status": "ready", "source": source},
            "ownership": {"status": "recipient", "source": source},
        }
        binding = {"session_id": "native"}
        current = {"current_binding_id": "binding", "execution_bindings": {"binding": binding}}
        operation = {
            "id": "send", "outcome": "submitted",
            "request": {"task_id": "work", "recipient": "sailor", "release_id": "release",
                        "binding_id": "binding", "session_id": "native",
                        "binding_digest": unified.digest(binding)},
        }
        runtime = {"tasks": {"work": current}, "operations": {"send": operation}}
        facts = [takeover, owner, release, handoff]
        execution_facts.validate_fact(handoff, facts[:-1])
        self.assertEqual(execution_facts.project(facts, runtime)["reported_owner"], "sailor")
        self.assertEqual(
            execution_facts.project(facts, runtime, task_id="work")["reported_owner"],
            "sailor",
        )
        self.assertEqual(
            execution_facts.project(facts, runtime, task_id="next")["reported_owner"],
            "captain",
        )
        self.assertFalse(execution_facts.project(facts)["handoff_reported_complete"])
        other_release = {**release, "id": "other-release", "task_id": "next"}
        separate = [*facts[:-1], other_release]
        execution_facts.validate_fact(handoff, separate)
        self.assertEqual(
            execution_facts.project([*separate, handoff], runtime, task_id="work")[
                "reported_owner"
            ],
            "sailor",
        )
        for field in ("receipt", "execution_ready", "monitor_ready", "ownership"):
            for evidence in (
                {"status": "unknown", "source": source},
                {**handoff[field], "source": {"kind": "caller_judgment", "ref": "inferred"}},
            ):
                with self.subTest(field=field, evidence=evidence):
                    pending = {**handoff, field: evidence}
                    projected = execution_facts.project([*facts[:-1], pending], runtime)
                    self.assertFalse(projected["handoff_reported_complete"])
                    self.assertEqual(projected["reported_owner"], "captain")
        operation["outcome"] = "unknown"
        with self.assertRaisesRegex(LbError, "reconcile unknown"):
            execution_facts.validate_handoff_operation(handoff, release, runtime)
        operation["outcome"] = "submitted"
        current["current_binding_id"] = "replacement"
        with self.assertRaisesRegex(LbError, "current recipient binding"):
            execution_facts.validate_handoff_operation(handoff, release, runtime)
        report = execution_facts.project(facts, runtime)
        self.assertFalse(report["handoff_reported_complete"])
        self.assertEqual(report["reported_owner"], "captain")
        new_release = {**release, "id": "replacement-release"}
        with self.assertRaisesRegex(LbError, "superseded release"):
            execution_facts.validate_fact(handoff, [*facts, new_release])

    def test_unknown_any_task_prevents_redelegation(self):
        with self.assertRaises(LbError):
            task_send_guard(
                {
                    "operations": {
                        "old": {
                            "outcome": "unknown",
                            "request": {"task_id": "old-task"},
                        }
                    }
                },
                "new-task",
                "new-op",
                {},
            )

    def test_id_conflict_and_submitted_replay(self):
        request = {"task_id": "a", "binding_id": "b"}
        ex = {"operations": {"op": {"outcome": "submitted", "request": request}}}
        self.assertIsNotNone(task_send_guard(ex, "a", "op", request))
        with self.assertRaises(LbError):
            task_send_guard(ex, "a", "op", {"task_id": "other"})

    def test_submitted_delivery_requires_business_action_evidence(self):
        ex = {
            "operations": {
                "old": {
                    "outcome": "submitted",
                    "request": {"task_id": "a", "binding_id": "old"},
                    "receipt": {"transport": "submitted"},
                }
            }
        }
        request = {"task_id": "a", "binding_id": "new"}
        with self.assertRaisesRegex(LbError, "no business-action outcome"):
            task_send_guard(ex, "a", "new-op", request)
        ex["facts"] = [
            {"kind": "business-action", "operation_id": "old", "outcome": "started"}
        ]
        self.assertIsNone(task_send_guard(ex, "a", "new-op", request))
        with self.assertRaisesRegex(LbError, "original operation ID"):
            task_send_guard(ex, "a", "new-op", ex["operations"]["old"]["request"])

    def test_first_send_without_confirmation_or_preflight_stops_before_host(self):
        self.assert_first_send_stops_before_host("")

    def test_first_send_with_route_level_dialogue_blocker_stops_before_host(self):
        self.assert_first_send_stops_before_host(
            "- [ ] 🔮 Confirm the scope of a later task\n"
        )

    def test_changes_between_live_check_and_intent_prevent_send(self):
        self.assert_first_send_stops_before_host("", change_before_intent="document")

    def test_concurrent_intent_occupies_execution_version(self):
        self.assert_first_send_stops_before_host("", change_before_intent="execution")

    def test_legacy_send_checks_versions_before_control_or_intent(self):
        root = Path("/example")
        doc = parse_text(b"# Work\n", root / "log.md", root)
        thinking = Mock()
        thinking.path.read_bytes.return_value = thinking.data
        dispatch = {
            "id": "dispatch",
            "task_id": "task",
            "owner": "worker",
            "status": "prepared",
            "scope": "Read fixture",
            "exclusions": [],
            "inputs": [],
            "completion": "Report",
            "escalation": "Report blocker",
        }
        binding = {
            "machine": "local",
            "workspace_id": "w1",
            "tab_id": "w1:t1",
            "pane_id": "w1:p1",
            "agent_id": "worker",
            "session_id": "session",
        }
        with (
            patch(
                "logbook_cli.execution.read",
                return_value=(doc.path, b"", {"operations": []}),
            ),
            patch("logbook_cli.execution.require_token"),
            patch("logbook_cli.execution.require_delegation"),
            patch(
                "logbook_cli.execution.projection",
                return_value={"takeover": None, "handoff": None},
            ),
            patch("logbook_cli.lifecycle.get", return_value={"value": "active"}),
            patch("logbook_cli.repository.require_synced", return_value=(doc, None)),
            patch(
                "logbook_cli.unified.locate",
                return_value=(doc.path, {"execution": {"operations": {}}}),
            ),
            patch("logbook_cli.services.readiness.require_ready"),
            patch(
                "logbook_cli.services.task_coordination.launcher_versions",
                return_value=(CliIdentity("1.2.3", "a" * 64), CliIdentity(None, None)),
            ),
            patch("logbook_cli.services.transport.herdr.control") as host,
            patch("logbook_cli.execution.write") as write,
        ):
            with self.assertRaisesRegex(LbError, "recipient CLI unknown"):
                send(
                    doc,
                    thinking,
                    dispatch,
                    binding,
                    "Read fixture",
                    "op",
                    "token",
                    "session",
                    "observation",
                    False,
                )
        host.assert_not_called()
        write.assert_not_called()

    def test_version_mismatch_blocks_before_host(self):
        self.assert_first_send_stops_before_host("", versions=("1.2.3", "1.2.4"))

    def test_unknown_version_blocks_before_host(self):
        for versions in ((None, "1.2.3"), ("1.2.3", None)):
            with self.subTest(versions=versions):
                self.assert_first_send_stops_before_host("", versions=versions)

    def test_same_version_reaches_host_on_current_replacement_binding(self):
        self.assert_first_send_stops_before_host(
            "", versions=("1.2.3", "1.2.3"), replacement=True
        )

    def test_same_version_with_different_or_unknown_implementation_blocks(self):
        for implementation in ("b" * 64, None):
            with self.subTest(implementation=implementation):
                self.assert_first_send_stops_before_host(
                    "",
                    versions=("1.2.3", "1.2.3"),
                    recipient_implementation=implementation,
                )

    def test_started_same_binding_followup_keeps_transport_without_version_probe(self):
        self.assert_first_send_stops_before_host("", followup=True)

    def test_followup_permission_refusal_blocks_transport(self):
        self.assert_first_send_stops_before_host("", followup=True, denied=True)

    def test_task_release_allows_actual_send_after_captain_takeover(self):
        self.assert_first_send_stops_before_host("", released_takeover=True)

    def test_task_release_with_conflicting_ownership_blocks_send(self):
        self.assert_first_send_stops_before_host(
            "", released_takeover=True, ownership_conflict=True
        )

    def test_completed_handoff_cannot_resend_the_same_message_with_new_id(self):
        request = {"task_id": "task", "binding_id": "binding", "message_digest": "digest"}
        ex = {
            "operations": {"first": {
                "outcome": "submitted", "request": {**request, "release_id": "release"},
            }},
            "facts": [{"kind": "business-action", "operation_id": "first", "outcome": "started"}],
        }
        with self.assertRaisesRegex(LbError, "original operation ID"):
            task_send_guard(ex, "task", "duplicate", request, released=True)
        self.assertIsNone(task_send_guard(
            ex, "task", "new-release", {**request, "release_id": "later"}, released=True
        ))

    def test_remote_probe_and_transport_share_one_resolved_machine(self):
        self.assert_first_send_stops_before_host(
            "", versions=("1.2.3", "1.2.3"), replacement=True, remote=True
        )

    def test_replay_and_unknown_delivery_do_not_probe_versions(self):
        for outcome in ("submitted", "unknown"):
            with self.subTest(outcome=outcome):
                self.assert_first_send_stops_before_host("", prior_outcome=outcome)

    def assert_first_send_stops_before_host(
        self,
        later_task,
        change_before_intent=None,
        *,
        versions=None,
        replacement=False,
        prior_outcome=None,
        recipient_implementation="a" * 64,
        followup=False,
        remote=False,
        denied=False,
        released_takeover=False,
        ownership_conflict=False,
    ):
        root = Path("/example")
        markdown = "# Work\n\n## Stage 1\n\n- [ ] Prepare fixture\n" + later_task
        doc = parse_text(markdown.encode(), root / "log.md", root)
        task = doc.stages[0].tasks[0]
        binding = {
            "machine": "local",
            "subject": {"kind": "agent", "subject_id": "worker"},
            "session_id": "session",
        }
        envelope = {
            "identity": {"run_id": "run"},
            "execution": {
                "operations": {},
                "tasks": {
                    "task": {
                        "current_binding_id": "binding",
                        "execution_bindings": {"binding": binding},
                    }
                },
            },
        }
        binding_id = "binding"
        if replacement:
            binding["machine"] = "local"
            binding_id = "replacement"
            runtime = envelope["execution"]["tasks"]["task"]
            runtime["current_binding_id"] = binding_id
            runtime["execution_bindings"][binding_id] = binding = {
                **binding,
                "session_id": "replacement-session",
                "work_context": {
                    "working_directory": "/example",
                    "cli_launcher": "/example/tools/lb",
                },
            }
        if remote:
            binding.update(machine="saved", server="remote-seat")
        session = binding["session_id"]
        if followup:
            operations = envelope["execution"]["operations"]
            operations["prior"] = {
                "request": {"task_id": "task", "binding_id": binding_id},
                "outcome": "submitted",
            }
            envelope["execution"]["facts"] = [
                {
                    "kind": "business-action",
                    "operation_id": "prior",
                    "outcome": "started",
                }
            ]
        if released_takeover:
            envelope["execution"]["operations"]["captain"] = {
                "request": {"task_id": "task"},
                "outcome": "submitted",
                "provenance": "takeover",
            }
            envelope["execution"]["facts"] = [{
                "id": "owner", "kind": "ownership", "owner": "captain",
                "source": {"kind": "runtime_observation", "ref": "observed owner"},
                "conflicts": ownership_conflict, "settled": True,
            }]
        release = {"scope": "task", "id": "release"} if released_takeover else None
        expect_submission = replacement or (released_takeover and not ownership_conflict) or (followup and not denied)
        if prior_outcome:
            envelope["execution"]["operations"]["operation"] = {
                "id": "operation",
                "outcome": prior_outcome,
                "request": {
                    "task_id": "task",
                    "binding_id": binding_id,
                    "run_id": "run",
                    "recipient": "worker",
                    "session_id": session,
                    "binding_digest": unified.digest(binding),
                    "message_digest": hashlib.sha256(b"Prepare fixture").hexdigest(),
                },
            }
        message_file = Mock()
        message_file.read_text.return_value = "Prepare fixture"
        changed = parse_text((markdown + "\nChanged route.\n").encode(), doc.path, root)
        synced = [(doc, task), (doc, task), (changed, task)]
        tokens = ["execution-token", "occupied-token"]

        def attempt_transport(*args, before_mutation):
            before_mutation()
            self.fail("adapter persisted intent for a changed document")

        with (
            patch(
                "logbook_cli.repository.require_synced",
                side_effect=synced if change_before_intent == "document" else None,
                return_value=(doc, task),
            ),
            patch("logbook_cli.document.safe_path", return_value=message_file),
            patch("logbook_cli.unified.writer", side_effect=lambda *a: nullcontext()),
            patch("logbook_cli.unified.publish_run") as publish,
            patch(
                "logbook_cli.unified.locate", return_value=(root / "run.json", envelope)
            ),
            patch(
                "logbook_cli.unified.section_token",
                side_effect=tokens if change_before_intent == "execution" else None,
                return_value="execution-token",
            ),
            patch(
                "logbook_cli.services.task_coordination.native_binding",
                return_value=binding,
            ),
            patch("logbook_cli.lifecycle.get", return_value={"value": "active"}),
            patch(
                "logbook_cli.execution.require_delegation",
                side_effect=LbError("delegation restricted") if denied else None,
                return_value=release,
            ) as delegation,
            patch(
                "logbook_cli.services.task_coordination.launcher_versions",
                return_value=(
                    CliIdentity(versions[0], "a" * 64),
                    CliIdentity(versions[1], recipient_implementation),
                )
                if versions
                else (
                    CliIdentity("1.2.3", "a" * 64),
                    CliIdentity("1.2.3", "a" * 64),
                ),
            ) as read_versions,
            patch(
                "logbook_cli.adapters.herdr.invoke",
                return_value=[
                    {
                        "id": "profile-id",
                        "label": "saved",
                        "session": "remote-seat",
                        "enabled": True,
                        "target": "worker.example.org",
                    }
                ],
            ) as resolve,
            patch("logbook_cli.observation.action_lock", return_value=nullcontext()),
            patch(
                "logbook_cli.services.transport.herdr.control", return_value={}
            ) as host,
        ):
            from logbook_cli.services.readiness import require_ready

            with patch(
                "logbook_cli.services.readiness.require_ready",
                wraps=(
                    None if change_before_intent or versions or released_takeover
                    else require_ready
                ),
            ) as ready:
                if change_before_intent:
                    host.side_effect = attempt_transport
                elif expect_submission:

                    def submit(*args, before_mutation):
                        before_mutation()
                        return {"receipt": {"id": "receipt"}}

                    host.side_effect = submit

                def send():
                    return send_task(
                        root,
                        "log.md",
                        "task",
                        binding_id,
                        "operation",
                        "execution-token",
                        session,
                        "observation",
                        "message.md",
                    )

                if prior_outcome == "submitted":
                    self.assertTrue(send().value["replayed_record"])
                elif denied:
                    with self.assertRaisesRegex(LbError, "delegation restricted"):
                        send()
                elif ownership_conflict:
                    with self.assertRaisesRegex(LbError, "ownership is unknown or conflicting"):
                        send()
                elif expect_submission:
                    self.assertEqual(send().value["operation"]["outcome"], "submitted")
                elif versions:
                    sender, recipient = versions
                    with self.assertRaisesRegex(
                        LbError,
                        f"sender CLI {sender or 'unknown'}.*recipient CLI {recipient or 'unknown'}",
                    ):
                        send()
                else:
                    with self.assertRaises(LbError):
                        send()
            if change_before_intent or expect_submission:
                host.assert_called_once()
                expected_machine = "profile-id" if remote else "local"
                self.assertEqual(host.call_args.args[0]["machine"], expected_machine)
            else:
                host.assert_not_called()
            if versions or change_before_intent or (released_takeover and not ownership_conflict):
                read_versions.assert_called_once_with(
                    {**binding, "machine": "profile-id"} if remote else binding,
                    "observation",
                    working_directory="/example" if replacement else None,
                    cli_launcher="/example/tools/lb" if replacement else None,
                    ssh_target="worker.example.org" if remote else None,
                )
            else:
                read_versions.assert_not_called()

            if followup:
                ready.assert_not_called()
                delegation.assert_called_once_with(doc, owner="worker", task_id="task")
            if released_takeover and not ownership_conflict:
                self.assertEqual(ready.call_count, 2)
                submitted = envelope["execution"]["operations"]["operation"]
                self.assertEqual(submitted["request"]["release_id"], "release")
            if remote:
                resolve.assert_called_once_with("local", "machine", "list", "--json")
            else:
                resolve.assert_not_called()
            self.assertEqual(publish.call_count, 2 if expect_submission else 0)


class RecipientLauncherVersionTests(unittest.TestCase):
    identity = CliIdentity("0.6.1-dev", "a" * 64)

    def test_reads_exact_launcher_only_for_current_live_observation(self):
        live = {
            "live_verified": True,
            "observation_token": "token",
            "observation": {"cwd": "/example/worker"},
        }
        launcher = "/approved/bin/alternate-lb"
        binding = {"machine": "local"}
        with (
            patch("logbook_cli.adapters.herdr.inspect", return_value=live) as inspect,
            patch("subprocess.run") as run,
        ):
            run.return_value = Mock(
                returncode=0, stdout=json.dumps(self.identity._asdict())
            )
            self.assertEqual(
                recipient_launcher_version(
                    binding, "token", "/example/worker", launcher, None
                ),
                self.identity,
            )
            run.assert_called_once_with(
                [launcher, "--build-identity"],
                cwd="/example/worker",
                capture_output=True,
                text=True,
                timeout=10,
            )
            run.reset_mock()
            inspect.reset_mock()
            self.assertEqual(
                recipient_launcher_version(
                    binding, "token", "/example/worker", None, None
                ),
                CliIdentity(None, None),
            )
            inspect.assert_not_called()
            for token, cwd in (
                ("stale", "/example/worker"),
                ("token", "/example/other"),
            ):
                self.assertEqual(
                    recipient_launcher_version(binding, token, cwd, launcher, None),
                    CliIdentity(None, None),
                )
            run.assert_not_called()

    def test_remote_probe_inspects_pinned_profile_and_quotes_declared_path(self):
        binding = {"machine": "profile-id", "server": "server"}
        live = {
            "live_verified": True,
            "observation_token": "token",
            "observation": {"cwd": "/example/with space"},
        }
        with (
            patch("logbook_cli.adapters.herdr.inspect", return_value=live) as inspect,
            patch(
                "subprocess.run",
                return_value=Mock(
                    returncode=0, stdout=json.dumps(self.identity._asdict())
                ),
            ) as run,
        ):
            self.assertEqual(
                recipient_launcher_version(
                    binding, "token", None, "/custom path/bin/lb", "worker.example.org"
                ),
                self.identity,
            )
            inspect.assert_called_once_with(binding)
            self.assertEqual(
                run.call_args.args[0][-2:],
                [
                    "worker.example.org",
                    "cd '/example/with space' && exec '/custom path/bin/lb' --build-identity",
                ],
            )

    def test_legacy_launcher_can_report_version_without_proving_build(self):
        with (
            patch(
                "logbook_cli.adapters.herdr.inspect",
                return_value={
                    "live_verified": True,
                    "observation_token": "token",
                    "observation": {"cwd": "/example"},
                },
            ),
            patch(
                "subprocess.run",
                side_effect=[
                    Mock(returncode=2, stdout=""),
                    Mock(returncode=0, stdout="0.6.1-dev"),
                ],
            ) as run,
        ):
            version = recipient_launcher_version(
                {"machine": "local"}, "token", "/example", "/example/bin/lb", None
            )
        self.assertEqual(version, CliIdentity("0.6.1-dev", None))
        self.assertEqual(
            [call.args[0][-1] for call in run.call_args_list],
            [
                "--build-identity",
                "--version",
            ],
        )

    def test_scope_mismatch_never_falls_back_to_local(self):
        with patch.object(
            herdr,
            "invoke",
            return_value=[{"id": "profile-id", "session": "other", "enabled": True}],
        ) as invoke:
            with self.assertRaisesRegex(LbError, "scope mismatch"):
                herdr.resolve_binding_scope(
                    {"machine": "profile-id", "server": "expected"}
                )
        invoke.assert_called_once_with("local", "machine", "list", "--json")


class CliBuildIdentityTests(unittest.TestCase):
    def test_digest_tracks_implementation_bytes_at_the_same_version(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = root / "logbook_cli"
            package.mkdir()
            source = package / "readiness.py"
            source.write_text("ACTION_SCOPED = False\n")
            with (
                patch.object(bootstrap, "__file__", str(package / "bootstrap.py")),
                patch.object(bootstrap, "cli_version", return_value="0.6.1-dev"),
            ):
                old = bootstrap.cli_identity()
                source.write_text("ACTION_SCOPED = True\n")
                new = bootstrap.cli_identity()
                self.assertEqual(new, bootstrap.cli_identity())
        self.assertEqual(old.version, new.version)
        self.assertNotEqual(old.implementation, new.implementation)

    def test_control_keeps_pinned_machine_after_label_changes(self):
        binding = {
            "machine": "receiver-label",
            "server": "seat",
            "workspace_id": "w1",
            "tab_id": "w1:t1",
            "pane_id": "w1:p1",
            "agent_id": "worker",
            "session_id": "session",
        }
        profiles = [
            {
                "label": "receiver-label",
                "id": "original",
                "session": "seat",
                "enabled": True,
                "target": "original.example.org",
            },
            {
                "label": "other",
                "id": "replacement",
                "session": "seat",
                "enabled": True,
                "target": "replacement.example.org",
            },
        ]
        calls = []

        def runtime(machine, *args, **kwargs):
            calls.append((machine, args))
            if args[:2] == ("machine", "list"):
                return profiles
            self.assertEqual(machine, "original")
            if args[:2] == ("pane", "get"):
                return {
                    "result": {
                        "pane": {
                            key: binding[key]
                            for key in ("workspace_id", "tab_id", "pane_id")
                        }
                    }
                }
            if args[:2] == ("agent", "get"):
                return {
                    "result": {
                        "agent": {
                            "agent": "worker",
                            "session_id": "session",
                            "agent_status": "idle",
                        }
                    }
                }
            if args[:2] == ("pane", "read"):
                return "ready"
            self.assertEqual(args[:2], ("agent", "prompt"))
            self.assertEqual(kwargs, {"mutation": True})
            return {"submitted": True}

        with patch.object(herdr, "invoke", side_effect=runtime):
            pinned, target = herdr.resolve_binding_scope(binding)
            token = herdr.inspect(pinned)["observation_token"]
            profiles[0]["label"], profiles[1]["label"] = "other", "receiver-label"
            herdr.control(pinned, "send", "session", token, "work", False)
        self.assertEqual(target, "original.example.org")
        self.assertEqual(calls[-1], ("original", ("agent", "prompt", "w1:p1", "work")))
        self.assertEqual(sum(machine == "local" for machine, _ in calls), 1)
