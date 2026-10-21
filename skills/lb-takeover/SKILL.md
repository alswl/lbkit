---
name: lb-takeover
version: 0.4.1-dev
description: "Captain personally tackles a scoped direction-setting problem, difficult investigation or repeatedly ineffective repair without delegating it. Use when asked to take over or work on it yourself, and automatically from authorized lb-push when direct Captain reasoning and execution are needed. Preserve authorization and safely recover Sailor ownership; hand back through lb-handback once the exit condition is met."
---

# Captain takes over execution

Read the [coordination contract](../../docs/installable/coordination.md#scoped-takeover-and-execution-handoff),
[configuration](../../docs/installable/configuration.md), current Logbook, applicable
spec/confirmation and host instructions. This changes execution ownership for a
bounded problem; Captain keeps coordination responsibility. A status query, plain
progress refresh or read-only preflight does not authorize entry.

1. Identify the problem/task/package, reason direct work is needed, permitted
   operations and observable exit condition. Do not take over routine work solely
   because a Sailor failed once or a wait expired. Existing scope/authorization
   suffices; ask only for a real new decision or permission. Unsettled core design
   returns to lb-plan/Admiral; experiments still need the bounded POC gate.
2. Recover the owning Sailor's candidate, worktree, uncommitted/user changes,
   prior attempts, live commands/side effects, review counts and open duties.
   Resolve the coordination root and isolated business worktree to actual absolute paths. Run document/runtime operations from the coordination root and business commands from the worktree; do not mix their relative paths in one assumed cwd. Use the host-declared runtime and its actual supported operations, following
   [execution rules](../lb-push/references/execution.md). Verify a safe pause or
   release of conflicting writes before taking ownership; an unanswered pause
   message is insufficient. Do not kill a running operation or reset changes.
   Preserve unrelated approved work and human dialogue/unsent input.
3. Verify the actual main-session model, deployment and data suitability. Use a
   suitable high-capability model; if unavailable or unverified, report the gap
   and prepare a permitted main-session transfer. Do not claim a model switch or
   use another agent/model-backed helper to solve the taken-over problem.
4. Checkpoint mode, task/scope, predecessor/current executor, candidate/worktree,
   exit condition and next action in existing bound Thinking/host records. Reuse
   the safe isolated business worktree. Perform the investigation, experiments,
   edits and self-checks personally, within host tool/browser and data rules.
   Logbook writes use the [document adapter](../lb-update/references/document-adapters.md),
   fresh context version_token, preview and readback; mode is not a new CLI field.
   After safe ownership is verified, maintain the task's current status detail
   with `🧑‍✈️ Captain 接手` (or the host's English wording), using the protected
   `task note` operation with preview/current token. Replace the matching current
   line via `--replace-line`; preserve human text and task first line. Do not show
   active takeover while safe ownership is still pending.
5. Reassess against the exit condition as facts change. Keep owning the hard
   problem until it is resolved, a concrete authorization/capability blocker
   remains, or Admiral redirects it. Do not delegate it back merely because it
   remains difficult. Report precise findings/blockers without inventing success.
6. At the exit condition, record actual changes, candidate identity, checks and
   limitations as Captain's direct result and automatically enter
   [lb-handback](../lb-handback/SKILL.md). A diagnosis may finish while the business
   operation remains failed. Self-checks never satisfy required independent review. Submission alone does not finish handoff: complete its receipt/readiness and current executor/status reconciliation, including replacing the active 🧑‍✈️ task detail, before reporting transfer complete.

## User-facing line guidance

In user-facing takeover findings, blockers and exit reports, apply the [locator guidance](../../docs/installable/coordination.md#human-facing-logbook-locators): identify the scoped Logbook task with its current `L50` position and name, and cite an exact status/criterion line when that is the subject of a decision. Keep runtime/worktree and result entries alongside it. This does not add a mode-switch confirmation.

After interruption, reread the checkpoint and actual disk/runtime state before
resuming. Reconcile pending commands and partial ownership changes; do not repeat
side effects or silently resume stale Sailor work. Report the scoped executor,
current result and next action briefly; switching modes does not reset counters,
complete human items, or expand commit/push/publication authorization.
