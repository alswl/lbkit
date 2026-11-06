# Herdr collaboration

Read `herdr --skill` from the installed binary and relevant command help. Runtime
syntax belongs there; this reference defines lb coordination boundaries.

## Prepare

Verify HERDR_ENV=1, binary/server compatibility, controlling runtime skill
installation/discovery and currency, selected runtime integration and actual
session identity separately. Retrieving bundled guidance is not installation.
Use the runtime's real configured skill paths/catalog; do not guess personal paths
or overwrite customization. Existing authorization governs setup, not automatic
hook refresh. A noncontrolling Sailor needs its instruction, not control skills.

Use host-approved runtime/model/wrapper, workspace and cwd. Preserve explicit
wrapper requirements: the native `agent open` convenience route supports selected
native runtimes only; it is not permission to substitute a generic executable for
a required wrapper. Consult current Herdr guidance for authorized wrappers.

## Open, close and correlate

Reuse a suitable existing Sailor session first. When lb-push or lb-handback needs
a new execution surface, prefer a Herdr tab in the selected workspace. Use the
installed Herdr guidance for tab creation and verify its returned tab/pane/session
identities without stealing focus. Use a split pane only when explicitly requested
or when tab creation is unavailable or unsuitable; report the concrete reason.

`lb agent open --input-file FILE --json` creates a no-focus sibling of the explicit
parent pane and starts the selected runtime. Input fields are machine, server,
parent_pane, absolute cwd, runtime and name. Verify returned identity/readiness.
Partial failure returns created pane IDs; inspect them instead of blindly opening
another session. Server scope must match the selected server; no local fallback.
This pane convenience route is the split-pane fallback, not the default tab path.

`lb agent close-session --input-file FILE --json` takes the returned binding and
explicit owned_panes. It verifies native identity, closes only the selected owned
pane and checks inventory. Pane disappearance alone does not prove all descendant
processes stopped. Existing dispatch-bound close/send routes remain compatible.
Neither convenience route changes a Task or authenticates human consent.

Use Herdr's existing input/read operations. Preserve existing guarded-send
journaling and uncertain-delivery protections when those routes apply. Captain
correlates explicit receiver acceptance to the actual instruction; delivery and
idle are not acceptance. Sailor neither reads Logbook nor writes Task state.

## Wait and continue

Read `lb agent observation context LOG --json`. Configure an absent Observation
with `lb agent observation configure LOG --input-file FILE --expect-version TOKEN`;
input is exactly targets with verified full bindings and baselines. Missing stable
document identity requires explicit migration. Before each mutation read fresh
Observation context; its token is not the document/execution token. Unchanged
targets need no reconfiguration.

Claude Code prefers native Monitor running `lb agent wait --log LOG --stream
--timeout SECONDS --expect-version TOKEN`. Without Monitor, run managed wait without
--stream in the foreground and reuse its live handle across host yields. Keep a
finite deadline within actual host limits; do not create another monitor Agent,
tab, daemon, model polling loop or terminal heartbeat.

On notification read fresh context: its token may already be stale. Saved unresolved
Events survive lost stdout, continuation and restart. Select the applicable action:

- `lb agent event defer LOG EVENT --action-id ID --input-file FILE --expect-version TOKEN`:
  reason and responsible_party; keeps the Event unresolved while other workers progress.
- `lb agent event resolve LOG EVENT --action-id ID --input-file FILE --expect-version TOKEN`:
  assessment for a non-question, or obsolete reason with evidence. It cannot claim an answer.
- `lb agent answer submit LOG EVENT --operation-id ID --input-file FILE --expect-version TOKEN`:
  question_id, revision and answer, through a supported native question protocol.
  Submit saves unknown intent before sending; no preceding prepare is needed.

The optional local Claude AskUserQuestion adapter requires explicit consumer-owned
PreToolUse/PostToolUse hook setup and a shared LBKIT_CLAUDE_QUESTION_DIR; installation
does not enable it. Read native question identifiers and structured questions from
the saved Event, then submit with its question.id and question.revision. Callback
acceptance alone remains unknown; only the matching native PostToolUse result can
confirm. Unconfigured workers and Codex question answering remain unavailable.
See the [CLI contract](../../../docs/installable/lb-cli.md#agent-wait-and-event-handling)
for setup, bounds and receipt retention. Explicitly name `capability_unavailable`
for an unsupported question/confirmation protocol, or `identity_missing` for an
unverified native binding, so the operator can distinguish the failure boundary. Never substitute prompt/send-keys or message reachability.
For uncertain delivery use `lb agent answer reconcile LOG OPERATION --expect-version TOKEN`;
it checks evidence and never resends. Same operation is replay; a new ID cannot
bypass unknown/submitted delivery. Editing, input sent, idle and working are not
question-specific confirmation.

For separately authorized external UI handling, first call `lb agent answer prepare
LOG EVENT --operation-id ID --input-file FILE --expect-version TOKEN` with answer_digest,
execution_owner, evidence and optional question_id. Prepare sends nothing. After the
authorized action, reconcile with --input-file RECEIPT and a fresh token, preserving
caller attribution. Protect human drafts and focus; never harvest drafts or blindly
repeat Enter. not_submitted needs affirmative non-submission evidence and proof the
external executor terminated.

Stop the host-owned listener and verify exit before target changes. Read context,
configure the complete desired target set, then restart wait. Unchanged and retired
cursors/history survive; pending affected Answers refuse replacement. Saved PID/status
is diagnostic, never proof of listener lock ownership.

Raw `lb agent wait --input-file FILE --timeout SECONDS --json` stays read-only. Keep
its complete next_input including unresolved_events; it has no managed lock/durable
recovery guarantee. Caller carry cannot clear managed Events. No observation, Event
resolution or Answer confirmation completes a business Task. Test Monitor delivery,
same-turn foreground handling and post-turn unprompted handling separately. A PID,
tool completion or bounded quiet interval proves no unattended wake or token-saving ratio.

See [the wait contract](../../../docs/installable/lb-cli.md#agent-wait-and-event-handling).
