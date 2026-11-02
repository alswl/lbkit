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

Save a bounded request with verified machine/server/workspace/tab/pane/agent/native
session bindings and optional baseline, then call
`lb agent wait --input-file FILE --timeout SECONDS --json`.
The command is read-only, returns on useful change and reaps only its own waiting
children. Reuse complete next_input unchanged; a missing token means observation
gaps, not lossless replay. Return reasons include change, timeout, interrupted and
unavailable; observations never establish acceptance or business completion.

Read attention targets, decide the appropriate next action, and retain other
workers. For needs-input, recover available authorized inputs or ask the responsible
person a focused question for the missing input. Preserve Captain's responsibility
and binding for paused in-flight work and late replies. Timeout does not justify
resend or killing Sailors. Use one bounded wait
rather than monitoring tabs, polling scripts or repeated model turns. Verify the
Captain host actually delivers tool completion; PID-only background execution
cannot certify unattended continuation. Report unsupported paths explicitly.

See [CLI contract](../../../docs/installable/lb-cli.md) and
[coordination contract](../../../docs/installable/coordination.md) for shared rules.
