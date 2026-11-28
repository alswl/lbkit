import unittest
from pathlib import Path
from unittest.mock import patch

from logbook_cli.document import LbError, parse_text
from logbook_cli.execution_facts import validate_fact, validate_new_fact
from logbook_cli.services.preflight_plan import current_plan, declaration, grant_source
from logbook_cli.services.readiness import _evaluate_evidence, evaluate, takeover_gap


class FirstStartReadinessTests(unittest.TestCase):
    def test_takeover_admission_requires_explicit_current_authority(self):
        instruction = {
            "id": "takeover", "kind": "takeover", "origin": "explicit",
            "source": {"kind": "human_instruction", "ref": "owner message"},
            "release_condition": None,
        }
        legacy = {
            **instruction, "origin": "automatic",
            "source": {"kind": "caller_judgment", "ref": "repair history"},
        }
        ownership = {
            "id": "owner", "kind": "ownership", "takeover_id": "takeover",
            "source": {"kind": "runtime_observation", "ref": "runtime check"},
            "owner": "coordinator", "conflicts": False, "settled": True,
        }
        release = {
            "id": "release", "kind": "delegation-release", "takeover_id": "takeover",
            "source": instruction["source"], "scope": "task", "task_id": "A",
            "recipient": "implementer", "condition_result_id": None,
        }
        validate_fact(legacy, [])
        with self.assertRaisesRegex(LbError, "explicit human instruction"):
            validate_new_fact(legacy, [])
        validate_new_fact(instruction, [])
        validate_new_fact(release, [legacy, ownership])
        for facts, task_id, actor, reason in (
            ([], "A", "coordinator", "explicit human"),
            ([legacy, ownership], "A", "coordinator", "explicit human"),
            ([instruction], "A", "coordinator", "sole execution ownership"),
            ([instruction, {**ownership, "conflicts": True}], "A", "coordinator", "sole execution ownership"),
            ([instruction, {**ownership, "owner": "other"}], "A", "other", "recorded Captain"),
            ([instruction, ownership, release], "A", "coordinator", "authorized handoff"),
            ([instruction, ownership, release], "B", "coordinator", None),
            ([instruction, ownership], "A", "coordinator", None),
        ):
            with self.subTest(facts=facts, task_id=task_id, actor=actor):
                gap = takeover_gap({"facts": facts, "captain": "coordinator"}, task_id, actor)
                if reason is None:
                    self.assertIsNone(gap)
                else:
                    self.assertIn(reason, gap or "")

    def test_new_legacy_release_requires_human_authorized_condition(self):
        judgment = {"kind": "caller_judgment", "ref": "repair history"}
        human = {"kind": "human_instruction", "ref": "owner message"}
        target = {"scope": "dispatch", "dispatch_id": "return", "recipient": "sailor"}
        condition = {"id": "exit", "source": judgment, **target}
        legacy = {
            "id": "takeover", "kind": "takeover", "origin": "automatic",
            "source": judgment, "release_condition": condition,
        }
        result = {
            "id": "result", "kind": "condition-result", "takeover_id": "takeover",
            "source": {"kind": "verified_result", "ref": "check", "verifier": "operator", "subject": "exit"},
            "condition_id": "exit", "satisfied": True,
        }
        release = {
            "id": "release", "kind": "delegation-release", "takeover_id": "takeover",
            "source": judgment, "condition_result_id": "result", **target,
        }
        validate_fact(release, [legacy, result])
        with self.assertRaisesRegex(LbError, "human-authorized condition"):
            validate_new_fact(release, [legacy, result])
        authorized = {**legacy, "release_condition": {**condition, "source": human}}
        validate_new_fact(release, [authorized, result])

    def test_readiness_uses_cutover_graph_and_invalidates_old_task_scope(self):
        from logbook_cli.repository import markdown_document
        from logbook_cli.services.route_scope import route_scope

        root = Path("/example")
        doc = markdown_document(
            b"# Work\n\n## Stage 1\n\n"
            b"- [ ] First\n    <!-- lb-task A -->\n"
            b"- [ ] Next\n    <!-- lb-task B -->\n    - Depends: A\n",
            root / "log.md", root,
        )
        before = route_scope(doc)
        evidence_row = {"source": "fixture", "scope": "B", "task_id": "B",
                        "route_ref": before["task_scopes"]["B"]}
        evidence = {
            "confirmations": [{**evidence_row, "status": "confirmed"}],
            "observations": [{**evidence_row, "status": "ready"}],
            "grants": [{**evidence_row, "status": "granted", "action": "dispatch", "actor": "runner"}],
        }
        run = {"identity": {}, "execution": {"operations": {}, "tasks": {}}}
        with patch("logbook_cli.services.readiness.read_bound_evidence", return_value=evidence):
            self.assertEqual(evaluate(doc, run, "B", "runner")["checks"]["dependency"], "blocked")
            doc.task_dependency_graph = {"A": [], "B": ["A"]}
            self.assertEqual(route_scope(doc), before)
            doc.task_dependency_graph = {"A": [], "B": []}
            changed = evaluate(doc, run, "B", "runner")["checks"]
            self.assertNotIn("dependency", changed)
            self.assertEqual(changed["confirmation"], "blocked")

    def test_managed_task_cannot_use_legacy_path_or_bypass_required_checks(self):
        scope = {"route_ref": "route", "task_scopes": {"A": "task-scope"}}
        plan = {
            "actor": "captain",
            "scope_ref": "task-scope",
            "candidate_ref": "candidate",
            "checks": [{"check_id": "qa-smoke", "subject_id": "qa"}],
        }
        evidence = {
            "confirmations": [
                {"route_ref": "route", "status": "confirmed", "source": "route review"}
            ],
            "grants": [
                {
                    "route_ref": "task-scope",
                    "scope": "A",
                    "task_id": "A",
                    "actor": "captain",
                    "action": "preflight-plan",
                    "status": "granted",
                    "source": "approved checks",
                    "candidate_ref": plan["candidate_ref"],
                    "checks": plan["checks"],
                }
            ],
        }
        managed = {"enrolled": ["A"], "plans": {}}
        self.assertIsNone(current_plan({}, "A", evidence, scope))
        with self.assertRaisesRegex(LbError, "required preflight checks"):
            current_plan({"preflight": managed}, "A", evidence, scope)
        managed["plans"]["A"] = {**plan, "source": "approved checks"}
        self.assertEqual(
            current_plan({"preflight": managed}, "A", evidence, scope), managed["plans"]["A"]
        )
        with self.assertRaisesRegex(LbError, "current confirmed Task scope"):
            current_plan(
                {"preflight": managed},
                "A",
                evidence,
                {**scope, "task_scopes": {"A": "replacement-scope"}},
            )
        empty = {**plan, "checks": []}
        with self.assertRaisesRegex(LbError, "exact preflight check set"):
            grant_source(evidence, scope, "A", empty)
        grant = evidence["grants"][0]
        grant["id"] = "original"
        replacement = {**grant, "id": "replacement", "checks": []}
        evidence["grants"].append(replacement)
        for disputed in (plan, empty):
            with self.assertRaisesRegex(LbError, "exact preflight check set"):
                grant_source(evidence, scope, "A", disputed)
        replacement["supersedes"] = "original"
        managed["plans"]["A"] = {**empty, "source": "approved checks"}
        self.assertEqual(
            current_plan({"preflight": managed}, "A", evidence, scope), managed["plans"]["A"]
        )

    def test_check_sets_have_stable_order_and_unique_ids(self):
        plan = {
            "actor": "captain",
            "scope_ref": "scope",
            "candidate_ref": "candidate",
            "checks": [
                {"check_id": "z", "subject_id": None},
                {"check_id": "a", "subject_id": "developer"},
            ],
        }
        self.assertEqual(declaration(plan)["checks"], plan["checks"][::-1])
        with self.assertRaisesRegex(LbError, "duplicate"):
            declaration({**plan, "checks": [plan["checks"][0]] * 2})

    def test_evidence_requires_nonempty_string_source(self):
        basis = {"source": "evidence", "route_ref": "route"}
        records = {
            "confirmations": [{**basis, "status": "confirmed"}],
            "observations": [{**basis, "task_id": "A", "status": "ready"}],
            "grants": [
                {
                    **basis,
                    "task_id": "A",
                    "actor": "worker",
                    "action": "dispatch",
                    "status": "granted",
                }
            ],
        }
        for collection, expected in (
            ("confirmations", "confirmation"),
            ("observations", "preflight"),
            ("grants", "authorization"),
        ):
            for source in (
                "",
                "   ",
                None,
                {"kind": "record", "ref": "evidence"},
                42,
                "valid",
            ):
                with self.subTest(collection=collection, source=source):
                    data = {
                        key: [dict(row) for row in rows]
                        for key, rows in records.items()
                    }
                    data[collection][0]["source"] = source
                    gaps = []
                    _evaluate_evidence(
                        data,
                        "route",
                        "A",
                        "worker",
                        "dispatch",
                        lambda kind, *args: gaps.append(kind),
                    )
                    self.assertEqual(gaps, [] if source == "valid" else [expected])

    def test_ready_and_blocked_observations_only_apply_to_their_action(self):
        basis = {"source": "observed evidence", "route_ref": "route"}
        ready = {**basis, "task_id": "A", "status": "ready"}
        missing = {**basis, "task_id": "A", "status": "missing", "object": "handoff"}
        value = {
            "confirmations": [{**basis, "status": "confirmed"}],
            "grants": [
                {
                    **basis,
                    "task_id": "A",
                    "actor": "runner",
                    "action": action,
                    "status": "granted",
                }
                for action in ("dispatch", "takeover")
            ],
        }
        for observations, action, expected in (
            ([ready], "dispatch", []),
            ([ready], "takeover", []),
            ([{**ready, "action": "dispatch"}], "takeover", ["preflight"]),
            ([{**ready, "action": "takeover"}], "dispatch", ["preflight"]),
            ([ready, {**missing, "action": "dispatch"}], "dispatch", ["preflight"]),
            ([ready, {**missing, "action": "dispatch"}], "takeover", []),
            ([ready, missing], "dispatch", ["preflight"]),
            ([ready, missing], "takeover", ["preflight"]),
        ):
            with self.subTest(observations=observations, action=action):
                gaps = []
                _evaluate_evidence(
                    {**value, "observations": observations},
                    "route",
                    "A",
                    "runner",
                    action,
                    lambda kind, message, *_: gaps.append(kind),
                )
                self.assertEqual(gaps, expected)

    def test_missing_prerequisites_are_independently_recoverable(self):
        basis = {"source": "observed evidence", "route_ref": "route"}
        valid = {
            "confirmations": [{**basis, "status": "confirmed"}],
            "observations": [{**basis, "task_id": "A", "status": "ready"}],
            "grants": [
                {
                    **basis,
                    "task_id": "A",
                    "actor": "worker",
                    "action": "dispatch",
                    "status": "granted",
                }
            ],
        }
        for collection, gap_kind in (
            ("confirmations", "confirmation"),
            ("observations", "preflight"),
            ("grants", "authorization"),
        ):
            with self.subTest(collection=collection):
                evidence = {**valid, collection: []}
                gaps = []
                _evaluate_evidence(
                    evidence,
                    "route",
                    "A",
                    "worker",
                    "dispatch",
                    lambda kind, message, *_: gaps.append((kind, message)),
                )
                self.assertEqual([kind for kind, _ in gaps], [gap_kind])
                self.assertTrue(gaps[0][1])
        valid["confirmations"].append({**basis, "status": "pending"})
        valid["observations"].append({**basis, "task_id": "B", "status": "missing"})
        gaps = []
        _evaluate_evidence(
            valid,
            "route",
            "A",
            "worker",
            "dispatch",
            lambda kind, _message, *_: gaps.append(kind),
        )
        self.assertEqual(gaps, ["confirmation"])

    def test_missing_route_and_unknown_operation_have_distinct_recovery(self):
        root = Path("/example")
        doc = parse_text(b"# Work\n", root / "log.md", root)
        run = {
            "identity": {"log_path": "log.md", "document_paths": ["log.md"]},
            "execution": {"operations": {}},
        }
        missing = evaluate(doc, run, "A")
        self.assertEqual(missing["decision"], "blocked")
        self.assertTrue(missing["recovery"])
        run["execution"]["operations"]["op"] = {
            "outcome": "unknown",
            "request": {"task_id": "A"},
        }
        uncertain = evaluate(doc, run, "A")
        self.assertEqual(uncertain["decision"], "reconcile")
        self.assertEqual(uncertain["gaps"][0]["object"], "operation")

    def test_records_must_cover_current_route_task_and_actor(self):
        basis = {"source": "record", "route_ref": "route"}
        evidence = {
            "confirmations": [{**basis, "status": "confirmed"}],
            "observations": [{**basis, "task_id": "task", "status": "ready"}],
            "grants": [
                {
                    **basis,
                    "task_id": "task",
                    "actor": "worker",
                    "action": "dispatch",
                    "status": "granted",
                }
            ],
        }
        for route, task, actor, expected in (
            ("route", "task", "worker", []),
            (
                "changed",
                "task",
                "worker",
                ["confirmation", "preflight", "authorization"],
            ),
            ("route", "task", "other", ["authorization"]),
        ):
            with self.subTest(route=route, actor=actor):
                gaps = []
                _evaluate_evidence(
                    evidence,
                    route,
                    task,
                    actor,
                    "dispatch",
                    lambda kind, message: gaps.append(kind),
                )
                self.assertEqual(gaps, expected)
        evidence["grants"].append({**evidence["grants"][0], "status": "revoked"})
        gaps = []
        _evaluate_evidence(
            evidence,
            "route",
            "task",
            "worker",
            "dispatch",
            lambda kind, message: gaps.append(kind),
        )
        self.assertEqual(gaps, ["authorization"])

    def test_takeover_intent_blocks_second_attempt_until_reconciled(self):
        from logbook_cli.document import LbError
        from logbook_cli.services.readiness import takeover_transition

        request = {
            "task_id": "task",
            "actor": "captain",
            "action": "takeover",
            "run_id": "run",
        }
        operations = {}
        first, may_start = takeover_transition(operations, "op", request, "reserve")
        self.assertTrue(may_start)
        operations["op"] = first
        self.assertFalse(takeover_transition(operations, "op", request, "reserve")[1])
        with self.assertRaises(LbError):
            takeover_transition(operations, "other", request, "reserve")
        operations["op"], _ = takeover_transition(
            operations, "op", request, "not_started", "runtime trace"
        )
        self.assertTrue(takeover_transition(operations, "other", request, "reserve")[1])

    def test_candidate_digest_detects_only_declared_input_changes(self):
        import hashlib
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from types import SimpleNamespace

        from logbook_cli.services.readiness import inputs_current

        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            path = root / "candidate"
            path.write_bytes(b"A")
            doc = SimpleNamespace(root=root, path=root / "log.md")
            evidence = {"candidate": hashlib.sha256(b"A").hexdigest()}
            (root / "later-input").write_text("changed")
            self.assertTrue(inputs_current(doc, evidence))
            path.write_bytes(b"B")
            with self.assertRaisesRegex(LbError, "observations.inputs.*candidate.*SHA-256"):
                inputs_current(doc, evidence)

    def test_input_keys_use_the_logbooks_project_and_reject_foreign_files(self):
        import hashlib
        from tempfile import TemporaryDirectory

        from logbook_cli.services.readiness import inputs_current

        with TemporaryDirectory() as directory:
            host = Path(directory).resolve()
            project = host / "project"
            nested = project / "nested"
            nested.mkdir(parents=True)
            (project / "mind.yaml").touch()
            (nested / "mind.yaml").touch()
            log = project / "log.md"
            candidate = project / "candidate"
            candidate.write_bytes(b"snapshot")
            (nested / "candidate").write_bytes(b"snapshot")
            decoy = host / "candidate"
            decoy.write_bytes(b"snapshot")
            digest = hashlib.sha256(b"snapshot").hexdigest()
            for root in (host, project):
                doc = parse_text(b"# Work\n", log, root)
                self.assertTrue(inputs_current(doc, {"candidate": digest}))
            (project / "escape").symlink_to(decoy)
            (project / "nested-alias").symlink_to(nested / "candidate")
            for key, reason in (
                (str(candidate), "project-relative"),
                ("../candidate", "project-relative"),
                ("nested/candidate", "outside the Logbook project"),
                ("nested-alias", "outside the Logbook project"),
                ("escape", "escapes the root"),
            ):
                with self.subTest(key=key), self.assertRaises(LbError) as error:
                    inputs_current(doc, {key: digest})
                for part in ("observations.inputs", key, str(project), reason):
                    self.assertIn(part, str(error.exception))
            candidate.unlink()
            doc = parse_text(b"# Work\n", log, host)
            with self.assertRaisesRegex(LbError, "observations.inputs.*candidate.*does not exist"):
                inputs_current(doc, {"candidate": digest})

    def test_first_start_blocks_unresolved_findings_and_checks_ready_inputs(self):
        import hashlib
        from tempfile import TemporaryDirectory

        from logbook_cli import task_identity

        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / "mind.yaml").touch()
            doc = parse_text(b"# Work\n\n## Stage 01\n\n- [ ] Build\n", root / "log.md", root)
            task = doc.stages[0].tasks[0]
            basis = {"source": "fixture", "route_ref": "route", "task_id": "A"}
            candidate = root / "build.txt"
            candidate.write_bytes(b"snapshot")
            digest = hashlib.sha256(b"snapshot").hexdigest()
            for action in ("dispatch", "takeover"):
                evidence = {
                    "confirmations": [{**basis, "status": "confirmed"}],
                    "grants": [{**basis, "actor": "worker", "action": action, "status": "granted"}],
                }
                for status, name, expected, reason in (
                    ("blocked", "build.txt", digest, "restore the input file"),
                    ("ready", "missing.txt", digest, "does not exist"),
                    ("ready", "build.txt", "0" * 64, "SHA-256 digest does not match"),
                    ("ready", "build.txt", digest, None),
                ):
                    with self.subTest(action=action, status=status, name=name, expected=expected):
                        evidence["observations"] = [{
                            **basis,
                            "status": status,
                            "object": name,
                            "clear_when": "restore the input file",
                            "criteria_digest": task_identity.criteria(task),
                            "skills": [],
                            "inputs": {name: expected},
                        }]
                        gaps = []
                        _evaluate_evidence(
                            evidence, "route", "A", "worker", action,
                            lambda kind, message, *_: gaps.append((kind, message)),
                            task=task, doc=doc,
                        )
                        if reason is None:
                            self.assertEqual(gaps, [])
                        else:
                            self.assertEqual(len(gaps), 1)
                            self.assertEqual(gaps[0][0], "preflight")
                            self.assertIn(reason, gaps[0][1])
                            if status == "ready":
                                for part in ("observations.inputs", name, str(root)):
                                    self.assertIn(part, gaps[0][1])

    def test_explicit_preflight_payload_is_relative_to_the_invocation_root(self):
        from tempfile import TemporaryDirectory

        from logbook_cli.services.agent_observation import _input

        with TemporaryDirectory() as directory:
            host = Path(directory).resolve()
            project = host / "project"
            project.mkdir()
            (project / "mind.yaml").touch()
            (host / "request.json").write_text('{"operation_id": "host"}')
            (project / "request.json").write_text('{"operation_id": "project"}')
            log = project / "log.md"
            host_doc = parse_text(b"# Work\n", log, host)
            project_doc = parse_text(b"# Work\n", log, project)
            self.assertEqual(_input(host_doc, "request.json"), {"operation_id": "host"})
            self.assertEqual(_input(project_doc, "request.json"), {"operation_id": "project"})
            self.assertEqual(
                _input(project_doc, str(project / "request.json")), {"operation_id": "project"}
            )
            argument = str(host / "request.json")
            with self.assertRaises(LbError) as error:
                _input(project_doc, argument)
            for part in ("--input-file", argument, str(project), "escapes the root"):
                self.assertIn(part, str(error.exception))

    def test_expiry_and_machine_changes_invalidate_ready_observation(self):
        from logbook_cli.services.readiness import observation_current

        current = {"machine": "example", "expires_at": "2999-01-01T00:00:00Z"}
        self.assertTrue(observation_current(current, "example"))
        self.assertFalse(observation_current(current, "other"))
        for expiry in ("2000-01-01T00:00:00Z", "2999-01-01T00:00:00", None):
            with self.subTest(expiry=expiry):
                self.assertFalse(
                    observation_current({**current, "expires_at": expiry}, "example")
                )

    def test_revocation_survives_route_change(self):
        evidence = {
            "confirmations": [
                {"source": "owner", "route_ref": "new", "status": "confirmed"}
            ],
            "observations": [
                {
                    "source": "check",
                    "route_ref": "new",
                    "status": "ready",
                    "task_id": "A",
                }
            ],
            "grants": [
                {
                    "source": "owner",
                    "route_ref": ref,
                    "task_id": "A",
                    "actor": "captain",
                    "action": "takeover",
                    "status": status,
                }
                for ref, status in (("old", "revoked"), ("new", "granted"))
            ],
        }
        gaps = []
        _evaluate_evidence(
            evidence,
            "new",
            "A",
            "captain",
            "takeover",
            lambda kind, message: gaps.append(kind),
        )
        self.assertEqual(gaps, ["authorization"])
