---
name: lb-takeover
version: 0.5.0-dev
description: "Use when asked to take over or do the work yourself: the current main Agent personally executes the whole authorized advancement, including later tasks, until human-authorized release. Also used by lb-push for automatic, problem-specific takeover. Recover ownership safely; repeated entry is idempotent."
---

Read the [document state and CLI failure recovery contract](../../docs/installable/document-state.md).
If lb is unavailable or crashes, notify the user and take over safe authorized work;
report pending writes and verification gaps instead of silently stopping or bypassing CAS.


# Captain takes over execution

Read the [coordination contract](../../docs/installable/coordination.md#scoped-takeover-and-execution-handoff),
[configuration](../../docs/installable/configuration.md), current Logbook, applicable
spec/confirmation and host instructions. Captain retains coordination while
executing directly. Status queries, progress refresh and read-only preflight do
not authorize entry.

A takeover request restricts delegation immediately; safe execution ownership is
a separate fact established in step 2.

1. Identify the problem/task/package, why direct work is needed, permitted
   operations and the observable exit condition. Explicit takeover covers the
   whole currently authorized advancement, including later lb-push tasks; only the
   human can narrow it or set a release condition. Automatic takeover needs a
   problem requiring Captain's direct reasoning; one Sailor failure or an elapsed
   wait is insufficient. Existing authorization suffices; ask only for a real new
   decision. Unsettled core design returns to lb-plan/Admiral; experiments still
   need the bounded POC gate.
2. With the lb CLI, read execution context and record the already-given takeover
   instruction as an [execution record](../../docs/installable/lb-cli.md#execution-state-in-project-json),
   adding a current ownership observation in the same batch when one exists. No
   extra confirmation or session metadata is needed. If this Captain already owns
   the scope, resume idempotently from the existing checkpoint, candidate, worktree
   and counters, after checking for actual conflicting operations. If no Sailor owns
   it, there is nothing to transfer. Otherwise recover the Sailor's candidate,
   worktree, uncommitted/user changes, prior attempts, live side effects, review
   counts and open duties. Resolve the coordination root and isolated business
   worktree to absolute paths; run document/runtime operations from the former and
   business commands from the latter. Follow [execution rules](../lb-push/references/execution.md)
   and [lifecycle operations](../../docs/installable/lifecycle-operations.md): preserve
   dispatch/run/package identity and use full Herdr IDs or a verified unique name,
   never list indexes. Prefer same-machine transfer; do not migrate work or
   credentials implicitly. Request release through the adapter's pause/release
   operation, never its package send. If pause is refused or unconfirmed, stop and
   report the pending owner. A request or receipt does not prove release. Do not
   kill operations, reset changes, or lose unrelated work and unsent human input.
3. Takeover changes execution responsibility, not the main Agent's identity or
   model; missing model metadata alone blocks nothing. Apply explicit host
   model/data restrictions to each actual operation and report a concrete blocker
   precisely. Do not claim a model switch or route taken-over work, including
   investigation, setup and self-checks, through any other agent, session, pane or
   model-backed helper; context/quota recovery is no exception. Leave a required
   independent review pending and report the conflict.
4. Record a newly established ownership observation, citing its source and the
   takeover fact ID, before business work; reuse an existing matching record. A
   caller judgment or requested pause is not a runtime observation. Thinking keeps
   reasoning, candidate and results. Use the [token workflow](../../docs/installable/lb-cli.md#target-file-tokens-and-a-minimal-recording-workflow),
   sync the page marker, update task facts through protected notes, and read both
   back. Non-CLI hosts use equivalent protected records. If evidence or recording
   is unavailable, report the gap without claiming active ownership.
5. Personally reproduce, investigate, edit and self-test in the verified isolated
   worktree, within host tool/browser and data rules. Keep owning the hard problem
   until it is resolved, a concrete blocker remains, or Admiral redirects it; do
   not delegate it back merely because it is difficult. Report precise findings
   without inventing success.
6. At each task's exit, record actual changes, candidate identity, checks and
   limitations as Captain's direct result; a diagnosis may finish while the
   business operation remains failed. During explicit takeover, continue later
   tasks personally: completion, skill switches and interruption are not handback.
   Enter [lb-handback](../lb-handback/SKILL.md) only on an explicit Admiral release or
   a met, previously authorized condition; automatic takeover enters it at its
   scoped exit. Preparing a handback permits no dispatch. Handback is complete only
   after receipt/readiness and ownership/status reconciliation; then drop `👨‍✈️`
   from the very next message.

## User-facing line guidance

The [shared presentation and release rules](../../docs/installable/coordination.md#scoped-takeover-and-execution-handoff)
apply to both progress messages and the final reply; changing a task marker alone
does not release advancement-wide takeover.

In user-facing takeover findings, blockers and exit reports, apply the [locator guidance](../../docs/installable/coordination.md#human-facing-logbook-locators): identify the scoped Logbook task with its current `L50` position and name, and cite an exact status/criterion line when that is the subject of a decision. Keep runtime/worktree and result entries alongside it. This does not add a mode-switch confirmation.

After interruption, reread the checkpoint and actual disk/runtime state before
resuming. Reconcile pending commands and partial ownership changes; do not repeat
side effects or silently resume stale Sailor work. Report the scoped executor,
current result and next action briefly; switching modes does not reset counters,
complete human items, or expand commit/push/publication authorization.
