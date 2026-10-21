---
name: lb-status
version: 0.4.1-dev
description: "Check project progress, executor status, blockers, and the next item, maintaining emoji and a few fact fragments; when context usage is found above 80%, hand off to lb-push for automatic GC. When the user explicitly asks read-only, report only — no checkbox or acceptance changes; deep plan review belongs to lb-plan."
---

Captain maintains the Logbook goal/route and coordination; Sailors normally execute business work. Authorized scoped Captain execution follows the [takeover and handoff contract](../../docs/installable/coordination.md#scoped-takeover-and-execution-handoff). Align the actual executor’s current result (task/package, result, conditions, outcome and gaps) before recording completion. Status/update-only requests start no business work or execution-mode switch.


# Check project status

In the status brief, visibly print `🧑‍✈️ Captain` when verified records show active takeover or handoff awaiting receipt/readiness. Identify pending ownership explicitly; the emoji alone is not proof. Explicit read-only requests still write no files.

mode is recorded (per the records) or live (joining approved live observation). When the user explicitly wants records only, use recorded; for ordinary progress queries, default to live when an identifiable dispatched executor exists, otherwise recorded. An explicit request for live observation also uses live. When query capability is unavailable, report "live status unknown"; do not repair the runtime environment.

Observation mode and write permission are separate: both recorded/live may maintain emoji and a few fact fragments; when the user explicitly says "read-only / no changes", write no files.

The first line of an existing todo must never be rewritten, appended to, or trimmed, and this entry point never touches checkboxes. Under a task, add only minimal status, blocker, or artifact links; observation process and detailed evidence go into the corresponding Thinking, never piled into main-logbook sub-items.

## Inputs and prerequisites

Locate the designated or uniquely identifiable logbook and read the [configuration contract](../../docs/installable/configuration.md). Clarify only when the project is not unique; do not search business repositories for context. Before live observation, read the [observation workflow](references/observation.md); before local writes, read the [logbook format](../../docs/installable/logbook-format.md) and the [document adapter workflow](../lb-update/references/document-adapters.md). Specs already read this round and unchanged need not be reloaded.

## Workflow

1. Per the [CLI read workflow](../lb-update/references/document-adapters.md#cli-invocation-in-this-repository), run `context --json` and `check --json` on the current logbook, and read the source, authorization, and relevant returns to verify stages and the first item. Script output does not represent live processes or acceptance state.
2. In live mode, query the designated executor's status and recent activity through the adapter's read-only interface. Distinguish historical records from this observation; a single snapshot does not prove long-term stagnation — judge with time and output. When it cannot be confirmed, mark it unknown faithfully; never treat a missing session identifier as proof that nothing is running.
3. Per the question's scope, verify stage status, item evidence, and gaps; sync derived emoji per the logbook format, maintaining brief status or fact fragments when needed. The exact local scale is left to the model, protecting human prose, goals, heading text, and manifest order; never rewrite whole pages, change checkboxes, or alter acceptance conclusions. Stage emoji use the CLI `sync` — carry the current token, preview, then write and check; other fragments follow local write protection. When explicitly read-only, report the diff only and never call `sync`, `task update`, or `task artifact` (including dry-run).
4. `idle`, `done`, or `blocked` does not prove acceptance completion. Live observation also checks context usage; above 80%, hand off automatically to lb-push's session GC flow without re-confirmation — never substitute account quota or cumulative tokens for the context ratio, and report unknown when unknown. When explicitly read-only, report only and do not trigger GC. With `runtime.quota` configured, report each relevant provider's observed usage against its watermarks (or unknown) and any active pause; switching and pausing executors belongs to lb-push. For other stalls or unreturned handoffs, report the basis and recovery conditions; this entry point itself never sends keystrokes or tasks, creates no listeners, and runs no business checks.
5. Report the first unchecked item, its owner, and its prerequisites; never present a more urgent later item as the next one, and never auto-dispatch just because a task is ready.

## Output and stopping

Give a briefing per the question; when runtime state is involved, include the executor name and workspace/tab/pane, observation time or recent activity, blockers, and the next action. A single factual question does not require the full template, and focus is not reported. If local writes occurred, briefly describe the changes and unverified items; apart from the automatic GC above, pure queries never reverse into acceptance or advancement flows. Return a requested human-readable list in the briefing; do not create or refresh a companion checklist file. For read-only todo filtering use `bin/lb task list`, and for the next item `bin/lb task next`; still verify scheduling semantics against the logbook source.

## User-facing line guidance

Apply the [locator guidance](../../docs/installable/coordination.md#human-facing-logbook-locators) in the briefing: identify the Logbook and pair the current/first unchecked task, blockers and next human action with verified `L50` positions. In a requested task list, include each listed task's line. A project-wide summary or runtime-only factual answer need not enumerate task lines; read-only requests remain read-only.

## Execution ownership

Read existing takeover/handoff checkpoints when applicable. Report the current
mode, scoped executor, exit condition, pending transfer and next action; show 🧑‍✈️ for confirmed Captain takeover (including pending handoff), never infer ownership from the emoji alone; stale or
conflicting records leave ownership unknown until read-only reconciliation.
This entry does not trigger takeover, business repair or handoff dispatch.
Captain self-checks do not satisfy a required independent Sailor review.
