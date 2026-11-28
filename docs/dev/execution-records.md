# Execution records and runtime boundaries

## Responsibility and evidence

The execution CLI records attributed facts and computes delegation constraints.
Those record commands do not orchestrate runtime pause/resume or an entire
handoff. Separate Herdr operations open scoped sessions, close owned resources
and perform one-shot read-only waiting. Compatible dispatch-bound input retains
guarded-send journaling. It cannot establish exclusive execution ownership or independent
review completion. A successful file write must not claim those capabilities.

Recording facts and controlling a runtime are separate effects. A record write
cannot certify exclusive ownership, pause/resume support or a complete handoff.
`record` accepts domain facts, not a requested phase or a `verified=true` flag.
Caller facts are always attributed to the caller, including reports of runtime
observations or verified checks. The CLI validates their structure and references;
it cannot authenticate human consent or independently verify their meaning.
Only an adapter result collected by this process is marked adapter-produced, and
that assurance applies to transport only. A saved binding is not a live observation.

## Invariants

- State lives in project `lb/<name>.json`, with explicit Logbook/Thinking bindings.
- Explicit takeover restricts the entire authorized advancement. Task completion,
  skill switches, missing session/model metadata and restart do not release it.
- New first-start reservations require explicit takeover as well as the action
  grant and sole observed Captain ownership. Retained automatic facts can still
  support readback, operation reconciliation and authorized handback. No state
  migration is needed. Use aligned launchers because older binaries lack the
  explicit takeover guard.
- Human instructions already in the conversation can be recorded directly. Recording
  them is not a request for renewed permission. Unknown authorization is a blocker;
  an unrecorded but already available instruction is a recording task.
- A stable fact ID is immutable. Identical retries do nothing; changed content under
  the same ID is refused. No runtime calls occur during recording or replay.
- Authorization to delegate and observed ownership are independent. A release permits
  only its nominated recipient/dispatch until an attributed complete handoff is
  recorded. A dispatch-only release never opens unrelated dispatches.
- A caller assertion alone cannot be upgraded to a runtime observation or verified
  result by the CLI. Every projection states its evidence origin and limitations.
- An unresolved transport intent prevents another send, including under a new ID.
  A receipt does not prove readiness, ownership transfer, review or acceptance.
- Execution writes use their current context token and a local writer lock for
  cooperating CLI mutations. Document edits and explicit projection sync follow
  the [document-state contract](../installable/document-state.md). Neither boundary
  is a distributed lock or a transaction spanning runtime effects and files.

## Complete workflows

**Already-owned takeover.** Record the human instruction and current ownership
observation in one batch, retaining a stable logical Captain identity. Session/model
metadata is optional here; session identity remains necessary only for the runtime
control that needs it. Repeating the same batch changes no bytes or counters and
never pauses the current Agent. Changed facts require new IDs, not editing history.

**Initial pause fails.** Record the takeover instruction immediately to constrain
future dispatch. Use the host's actual pause capability separately. Record unknown
or conflicting ownership as observed; do not promote an attempted pause into safe
ownership. No business work or handoff follows from a saved instruction alone.

**Current task finishes; next needs independent review.** Retain the takeover fact.
The next dispatch remains blocked. Preserve the review as pending; self-tests do
not satisfy it. Ordinary next work stays with Captain. No new approval is requested
merely to continue the already-authorized personal work.

**Bounded handback.** Record the existing human release instruction, naming the
recipient/dispatch. Alternatively reference the condition granted by the takeover
instruction and an attributed check result for that exact condition. Record the
remaining package through existing dispatch commands. Send only after runtime
preconditions are actually met. Record receipt, recipient readiness, monitor
readiness and ownership independently, with evidence references. A complete set is
reported as caller-reported handoff completion, not CLI-verified transfer. Reuse
original permission on recovery; completion of a task never supplies permission.

**Send timeout or interruption.** `agent send` requires a stable operation ID and
JSON token in addition to the Thinking token; it reuses recorded permission and
has no additional `--basis` confirmation. After live identity checks and before
transport, persist unknown intent with recipient/session and message/package digests.
On success persist the adapter receipt. Any failure after intent leaves unknown
state; an interrupt requires no cleanup to preserve this guard. Repeating a recorded
successful operation returns its receipt without sending; changing its payload is
refused. A new ID cannot evade an outstanding or successful send for the dispatch.
An attributed runtime reconciliation can resolve unknown to submitted/not-submitted;
only the latter permits a new attempt, still subject to current permission. Merely
inspecting an idle recipient is not proof of non-delivery.

**Partial writes and projections.** If intent cannot be saved, do not send. If runtime
succeeds but receipt persistence fails, expose the receipt and the pending recovery;
leave durable intent unknown. JSON mutations never silently edit Markdown. Current
Markdown defines document facts; explicitly synchronize its projection after an
authorized edit and report the two outcomes separately. A stale page marker
cannot supply execution permission or erase unknown delivery. Preserve human text
and report any unfinished task-note reconciliation separately.

## Explicit limits

Caller-recorded observations can be wrong; structural validation cannot authenticate
them. Direct host tools bypassing `lb`, other coordination logs, non-cooperating
writers and remote machines are outside the local gate. Carry the original bound
Logbook during cross-repository business work. No exactly-once delivery guarantee is
possible without runtime idempotency/receipt lookup. An unknown send may require
human/runtime investigation, but never re-approval of a permission already supplied.
The `agent close` path remains a separate one-shot control and is not a handoff.
