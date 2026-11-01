"""Open/close only explicitly selected owned resources; retain partial facts."""

import json

from coordination_helpers import CoordinationTest
from test_agent_wait_e2e import observation, target


class CollaborationLifecycleTest(CoordinationTest):
    def request(self, value):
        (self.root / "request.json").write_text(json.dumps(value))

    def test_open_returns_created_identity_without_dispatch(self):
        t = target()
        b = t["binding"]
        v = observation(t, "idle")
        v["foreground_cwd"] = str(self.root)
        self.script(
            [
                {
                    "argv": ["status"],
                    "responses": [
                        {
                            "stdout": {
                                "server": {
                                    "running": True,
                                    "session": "example-session",
                                }
                            }
                        }
                    ],
                },
                {
                    "argv": ["pane", "split"],
                    "responses": [{"stdout": {"result": {"pane": v}}}],
                },
                {
                    "argv": ["agent", "start"],
                    "responses": [{"stdout": {"result": {"agent": v}}}],
                },
                {
                    "argv": ["agent", "get"],
                    "responses": [{"stdout": {"result": {"agent": v}}}],
                },
                {
                    "argv": ["pane", "get"],
                    "responses": [{"stdout": {"result": {"pane": v}}}],
                },
            ]
        )
        self.request(
            {
                "machine": "local",
                "server": "example-session",
                "parent_pane": "w1:p9",
                "cwd": str(self.root),
                "runtime": "codex",
                "name": "example-worker",
            }
        )
        r = self.cli("agent", "open", "--input-file", "request.json")
        self.assertEqual(r["binding"], b)
        self.assertEqual(r["owned_panes"], ["w1:p1"])
        self.assertIn("--no-focus", self.calls()[2]["argv"])
        self.assertNotIn("prompt", str(self.calls()))

    def test_failed_start_retains_created_pane(self):
        v = observation(target(), "unknown")
        self.script(
            [
                {
                    "argv": ["status"],
                    "responses": [
                        {
                            "stdout": {
                                "server": {
                                    "running": True,
                                    "session": "example-session",
                                }
                            }
                        }
                    ],
                },
                {
                    "argv": ["pane", "split"],
                    "responses": [{"stdout": {"result": {"pane": v}}}],
                },
                {"argv": ["agent", "start"], "responses": [{"code": 1}]},
            ]
        )
        self.request(
            {
                "machine": "local",
                "server": "example-session",
                "parent_pane": "w1:p9",
                "cwd": str(self.root),
                "runtime": "codex",
                "name": "example-worker",
            }
        )
        r = json.loads(
            self.cli("agent", "open", "--input-file", "request.json", code=1).stdout
        )
        self.assertEqual(r["owned_panes"], ["w1:p1"])
        self.assertEqual(r["status"], "unknown")
        self.assertEqual(
            sum(
                c["kind"] == "start" and c["argv"][:2] == ["agent", "start"]
                for c in self.calls()
            ),
            1,
        )

    def test_close_refuses_unowned_pane_before_mutation(self):
        self.request({"binding": target()["binding"], "owned_panes": []})
        self.cli("agent", "close-session", "--input-file", "request.json", code=4)
        self.assertEqual(self.calls(), [])

    def close_runtime(self, *, changed=False, remaining=False, failed=False, server='example-session'):
        item = target()
        if changed:
            item['binding']['session_id'] = 'different-session'
        value = observation(item, 'idle')
        self.script([
            {'argv': ['status'], 'responses': [{'stdout': {'server': {'running': True, 'session': server}}}]},
            {'argv': ['pane', 'get'], 'responses': [{'stdout': {'result': {'pane': value}}}]},
            {'argv': ['agent', 'get'], 'responses': [{'stdout': {'result': {'agent': value}}}]},
            {'argv': ['pane', 'close'], 'responses': [{'code': 1} if failed else {'stdout': {'result': {}}}]},
            {'argv': ['pane', 'list'], 'responses': [{'stdout': {'result': {'panes': [value] if remaining else []}}}]},
        ])
        self.request({'binding': target()['binding'], 'owned_panes': ['w1:p1']})

    def test_changed_native_session_refuses_close(self):
        self.close_runtime(changed=True)
        self.cli('agent', 'close-session', '--input-file', 'request.json', code=4)
        self.assertFalse(any(c['argv'][:2] == ['pane', 'close'] for c in self.calls()))

    def test_server_scope_mismatch_refuses_close(self):
        self.close_runtime(server='another-server')
        self.cli('agent', 'close-session', '--input-file', 'request.json', code=4)
        self.assertFalse(any(c['argv'][:2] == ['pane', 'close'] for c in self.calls()))

    def test_successful_close_observes_absence_but_not_descendant_cleanup(self):
        self.close_runtime()
        result = self.cli('agent', 'close-session', '--input-file', 'request.json')
        self.assertEqual(result['status'], 'closed')
        self.assertEqual(result['remaining_owned_panes'], [])
        self.assertEqual(result['process_cleanup'], 'not independently verified')

    def test_failed_or_unconfirmed_close_retains_owned_resource(self):
        for options in ({'remaining': True}, {'failed': True}):
            with self.subTest(options=options):
                self.close_runtime(**options)
                result = json.loads(self.cli('agent', 'close-session', '--input-file', 'request.json', code=1).stdout)
                self.assertEqual(result['status'], 'unknown')
                self.assertEqual(result['remaining_owned_panes'], ['w1:p1'])
