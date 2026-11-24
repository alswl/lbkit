import unittest
from pathlib import Path

from logbook_cli.document import parse_text
from logbook_cli.services.readiness import _evaluate_evidence, evaluate


class FirstStartReadinessTests(unittest.TestCase):
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
        run = {"identity": {}, "execution": {"operations": {}}}
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
            doc = SimpleNamespace(root=root)
            evidence = {"candidate": hashlib.sha256(b"A").hexdigest()}
            (root / "later-input").write_text("changed")
            self.assertTrue(inputs_current(doc, evidence))
            path.write_bytes(b"B")
            self.assertFalse(inputs_current(doc, evidence))

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
