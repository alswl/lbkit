# Real Herdr E2E

This suite runs the current CLI against a real Herdr server and real coding agents.
It is separate from `test_agent_wait_e2e.py`, which uses an executable fake. Normal
unittest discovery never launches these live tests.

Run from an authorized Herdr-managed caller with `HERDR_ENV=1`, a compatible
running server, working runtime integrations and usable model credentials. The
tests use a disposable working directory and create no-focus panes. The example
configuration sets `agent_layout: tabs`, giving each agent a full-size tab in the
caller's workspace. The compatibility default is `siblings`; it refuses splits
that would leave an agent below 80 columns or 20 rows. They close only panes
created by this invocation. Model calls
incur the runtime's usual cost. Hooks, global settings and servers are not updated.

Copy `config.example.json` outside the checkout and configure each runtime's
actual Herdr kind and argument array. Wrapper arguments and provider selection
belong in that local file; never commit credentials, private endpoints or local
environment details. The default model is inherited unless the operator supplies
one. An optional `startup_keys` list may dismiss a known startup screen; it must
not be used to approve arbitrary dialogs or grant blanket trust.

Use full-size tabs for native question UI acceptance. Narrow panes can wrap a
question footer across lines and change Herdr's detection result. Capture the
actual pane dimensions and `herdr agent explain` alongside `agent get`; a layout
failure must not be reported as a missing question capability. The runner does not
normalize terminal text or override native state to make a test pass.

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

The Captain probe defaults to a two-second wait. Set `foreground_wait_seconds`
to 90 (with `turn_timeout` greater than 100) for a longer no-event window. Keep the
same turn open, use supported long foreground waits, and align inner process wait
and outer orchestration yield windows. A running handle is reused, never restarted.
The probe records requested/actual CLI duration and requires a subsequent handling
receipt; neither elapsed time nor a receipt certifies zero model polling. Preserve
the complete host tool trace to count early yields and model continuations. A
self-reported count is supplementary, not independent proof. The runner explicitly
leaves sustained suspension, UI classification and mid-tool steering unverified
without their separate evidence.

Captain foreground return and Herdr access are judged separately. A Captain that
receives an `unavailable` result and writes the matching receipt passes continuation;
its Herdr-readiness check remains `BLOCKED`. The generated command saves its actual
wait result, Herdr status stderr and a small caller-context diagnostic. Busy-agent
read failures fall back to the visible viewport to retain permission-dialog evidence.
Both `FAIL` and `BLOCKED` keep the overall run unsuccessful.
For feature acceptance configure two worker axes plus a separate `captain` runtime
object. The dedicated Captain observes both workers, never its own session. The
legacy reciprocal two-agent probe remains a compatibility check and does not
establish one-Captain/two-worker acceptance. Captain probes configure isolated
managed state and establish cursors before timing the wait.

Read failures and partial startup retain created pane IDs for cleanup. The runner
does not infer descendant-process cleanup from pane disappearance. A force-killed
runner may not finish teardown; inspect its `owned.json` and close only those
resources after verifying that they still belong to the run.


## Wait recovery acceptance

Runtime keys are short test labels, independent of `kind`; use `codex-a` and
`codex-b`, both with `kind: codex`, for two Codex workers. The runner validates the
calling pane before creating either worker. Stale inherited caller context is a
blocked prerequisite, never permission to use the focused pane or existing workers.
Every follow-up wait preserves `unresolved_events` with `targets` and `after`.

The automatic suite covers foreground return only. Complete these additional
host-specific cases using disposable workers and retain raw evidence outside the
checkout; do not count a design assertion as a live pass:

| Case | Required evidence |
|---|---|
| Same-turn no-event wait | Two verified workers, one long wait handle, inner/outer requested and effective yield windows, complete count of model continuations; do not hide host-enforced yields |
| Waiting UI | Captain remains working/waiting for a tool; distinguish an actual human-input blocked question from a tool wait using timestamped UI observations |
| Blocked question | Synthetic question, `agent_blocked` refusal, observed editor/submission states, matching accepted answer receipt |
| Reported but unhandled | Save a real needs_input return, continue without removing it, recover it from unresolved_events without a duplicate notification |
| User interjection | Test both input between tool calls and steer/queue during an outstanding tool call; retain timestamps, unchanged listener identity, complete bindings and unresolved checkpoint |
| Turn end | Captain final precedes wait completion, followed by a host-initiated new turn and actual handling receipt without a user prompt |
| Duplicate delivery | Replay the same result after a saved handling receipt; no second answer submission |

For a blocked UI, test only the synthetic question and known authorized answer;
inspect after each editing/submission action. Never automate repeated Enter based
on command exit status or touch a human draft. If the host lacks a question-aware
answer API or attributable receipt, record that capability gap.

Record active-turn and post-turn outcomes separately. A background command that
finishes without a resumed Captain demonstrates only command execution. State the
bounded observation window if no wake is observed; do not claim universal failure
or token savings. Graceful cancellation and forced loss also differ: only a saved
complete result supports lossless continuation from that point.

A useful host-only isolation test runs the actual CLI with two executable-fake
working observations for 90 seconds. Record process/session identity before and
after real user input, and the inner/outer tool returns. This tests the tool host
and recovery plumbing without touching live workers; it does not establish real
Herdr UI state or worker integration. Input between tool calls does not certify
steer/queue during a suspended call. Do not generalize a failed post-turn wake or
a bounded yield window into “Codex does not support waiting.”


## Managed acceptance dimensions

An isolated configuration may set `runtimes` to worker-a/worker-b (each with kind
and args), and `captain` to another runtime object. Exactly two worker axes are
required with a dedicated Captain. Use foreground_wait_seconds >=90 and a
turn_timeout with at least ten seconds additional handling room. Each probe creates
a disposable logbook, identifies it, configures managed observation with fresh CAS,
consumes initial gaps and invokes managed wait from the Captain.

Keep raw host tool traces with requested/effective nested yield windows and every
continuation. `validate_host_trace` checks listener continuity, separate suspended-
tool/between-call/Monitor interjection phases, and final-before-completion plus an
unprompted new turn and handling receipt for post-turn claims. It checks supplied
ordering only; trace shape cannot establish authentic capture or actual host support.
Missing original evidence remains unverified. Native Monitor, foreground and post-turn
trials remain separate. An unmapped native question/confirmation protocol blocks
positive automatic-answer acceptance; passing the refusal path cannot replace it.

### Optional native Claude Answer acceptance

Question-answer trials additionally require the explicitly configured local Claude
AskUserQuestion callbacks described in [the CLI contract](../../../docs/installable/lb-cli.md#agent-wait-and-event-handling).
The general runner never installs hooks. Use a separate disposable project and
owner-only runtime directory, configure only its project-local PreToolUse and
PostToolUse hooks, and inherit LBKIT_CLAUDE_QUESTION_DIR in both worker and driver.
Leave global settings and unrelated workers untouched. A targeted temporary driver
can exercise these cases through the same public CLI without adding hook setup to
the general topology runner:

1. Establish a genuine native Claude session, configure its complete binding and
   start managed wait. Request an actual AskUserQuestion; require needs_input with
   the matching native question ID/revision and structured questions.
2. Submit with fresh CAS. Require the matching actual PostToolUse structured
   answer before confirmed/Event resolved. Replay after the question disappears;
   count native acceptance callbacks to prove no extra submission.
3. Delay the PostToolUse receipt writer after capturing the real callback, then
   kill only the owned submitting CLI. Require durable unknown, same-ID read-only
   replay and different-ID delivery_unresolved. Release confirmation, reconcile
   without input and require atomic resolution with adapter provenance.
4. Separately use external prepare before authorized UI work. A draft without
   submission must remain unknown/pending; an actual native accepted result can
   support a caller-attributed receipt. Test lost receipt/replay and refusal to
   convert the external intent into automatic mode.

Retain timestamped whitelisted callback payloads and public CLI outputs only in
the temporary trial directory. Do not read unrelated/private session transcripts
or count a synthetic callback as live acceptance. Confirm no answer plaintext in
Observation/runtime records, then close only owned resources. Unit protocol tests
in test_claude_questions.py and test_claude_native_hook.py remain offline evidence.

A stale inherited caller is BLOCKED before resource creation. Never use the focused
pane or a business worker as a replacement caller. Startup trust/account/permission
gates require their actual owner; do not script blanket approval. Retain owned.json
and verify owned identities before cleanup after forced runner loss.
