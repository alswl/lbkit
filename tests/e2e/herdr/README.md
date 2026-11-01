# Real Herdr E2E

This suite runs the current CLI against a real Herdr server and real coding agents.
It is separate from `test_agent_wait_e2e.py`, which uses an executable fake. Normal
unittest discovery never launches these live tests.

Run from an authorized Herdr-managed caller with `HERDR_ENV=1`, a compatible
running server, working runtime integrations and usable model credentials. The
tests create no-focus sibling panes in the caller's tab, using a disposable
working directory. They close only panes created by this invocation. Model calls
incur the runtime's usual cost. Hooks, global settings and servers are not updated.

Copy `config.example.json` outside the checkout and configure each runtime's
actual Herdr kind and argument array. Wrapper arguments and provider selection
belong in that local file; never commit credentials, private endpoints or local
environment details. The default model is inherited unless the operator supplies
one. An optional `startup_keys` list may dismiss a known startup screen; it must
not be used to approve arbitrary dialogs or grant blanket trust.

```sh
uv run --locked python tests/e2e/herdr/run.py \
  --run-live --config /tmp/herdr-e2e.local.json \
  --output /tmp/herdr-e2e-results
```

Use `--cases core`, `--cases multi`, or `--cases captain` to rerun selected groups.
Multiple groups can be supplied. Recipient acceptance, native identity checks and
owned-resource cleanup always run, even when a group is selected.

The output directory must be new. It retains the candidate snapshot, generated
requests, raw command stdout/stderr, elapsed times, runtime identities, reply
snapshots, cleanup inventory and `report.json`. Keep it outside tracked content.
Exit 0 means every executed assertion passed and owned panes were reclaimed;
exit 1 means a failed or blocked assertion or incomplete cleanup; exit 2 means
invalid configuration or missing caller prerequisites. A blocked runtime is never
silently omitted from the result.

Assertions cover real recipient acceptance and identity, lost-context snapshots,
unchanged-state suppression and timeout, invalid continuation and changed-identity
refusal, interruption without stopping Sailors, multi-target observation, actual
working-to-settled delivery, and identity-checked close. The multi-target case
observes both agents working, verifies one settles while another is still working,
then observes the remaining agent's natural completion. Captain-host continuation
is a separate case: the runtime executes a real wait, receives its result and then
writes a receipt using a subsequent tool call. A detached process identifier alone
does not pass that case. Startup or tool-permission dialogs are retained as blocked
evidence rather than answered automatically.

Set a host command tool's foreground yield window longer than the two-second wait
used by the Captain probe. Returning a running session identifier before that
deadline does not establish result delivery or justify a fabricated receipt.

Captain foreground return and Herdr access are judged separately. A Captain that
receives an `unavailable` result and writes the matching receipt passes continuation;
its Herdr-readiness check remains `BLOCKED`. The generated command saves its actual
wait result, Herdr status stderr and a small caller-context diagnostic. Busy-agent
read failures fall back to the visible viewport to retain permission-dialog evidence.
Both `FAIL` and `BLOCKED` keep the overall run unsuccessful.
Captain probes require two accepted runtime axes: each Captain observes the other
Sailor rather than its own session.

Read failures and partial startup retain created pane IDs for cleanup. The runner
does not infer descendant-process cleanup from pane disappearance. A force-killed
runner may not finish teardown; inspect its `owned.json` and close only those
resources after verifying that they still belong to the run.
