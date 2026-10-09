---
name: lb-status
version: 0.1.0
description: Check project progress, executor status, blockers, and the next item, maintaining emoji and a few fact fragments; when context usage is found above 80%, hand off to lb-push for automatic GC. When the user explicitly asks read-only, report only — no checkbox or acceptance changes; deep plan review belongs to lb-plan.
---

# Check project status

mode is recorded (per the records) or live (joining approved live observation). When the user explicitly wants records only, use recorded; for ordinary progress queries, default to live when an identifiable dispatched executor exists, otherwise recorded. An explicit request for live observation also uses live. When query capability is unavailable, report "live status unknown"; do not repair the runtime environment.

Observation mode and write permission are separate: both recorded/live may maintain emoji and a few fact fragments; when the user explicitly says "read-only / no changes", write no files.

The first line of an existing todo must never be rewritten, appended to, or trimmed, and this entry point never touches checkboxes. Under a task, add only minimal status, blocker, or artifact links; observation process and detailed evidence go into the corresponding Thinking, never piled into main-logbook sub-items.

## Inputs and prerequisites

Locate the designated or uniquely identifiable logbook and read the [configuration contract](../../docs/configuration.md). Clarify only when the project is not unique; do not search business repositories for context. Before live observation, read the [observation workflow](references/observation.md); before local writes, read the [logbook format](../../docs/logbook-format.md) and the [document adapter workflow](../lb-update/references/document-adapters.md). Specs already read this round and unchanged need not be reloaded.

## Workflow

1. Per the [CLI read workflow](../lb-update/references/document-adapters.md#本仓-cli-调用), run `context --json` and `check --json` on the current logbook, and read the source, authorization, and relevant returns to verify stages and the first item. Script output does not represent live processes or acceptance state.
2. In live mode, query the designated executor's status and recent activity through the adapter's read-only interface. Distinguish historical records from this observation; a single snapshot does not prove long-term stagnation — judge with time and output. When it cannot be confirmed, mark it unknown faithfully; never treat a missing session identifier as proof that nothing is running.
3. Per the question's scope, verify stage status, item evidence, and gaps; sync derived emoji per the logbook format, maintaining brief status or fact fragments when needed. The exact local scale is left to the model, protecting human prose, goals, heading text, and manifest order; never rewrite whole pages, change checkboxes, or alter acceptance conclusions. Stage emoji use the CLI `sync` — carry the current token, preview, then write and check; other fragments follow local write protection. When explicitly read-only, report the diff only and never call `sync`, `task update`, or `task artifact` (including dry-run).
4. `idle`, `done`, or `blocked` does not prove acceptance completion. Live observation also checks context usage; above 80%, hand off automatically to lb-push's session GC flow without re-confirmation — never substitute account quota or cumulative tokens for the context ratio, and report unknown when unknown. When explicitly read-only, report only and do not trigger GC. For other stalls or unreturned handoffs, report the basis and recovery conditions; this entry point itself never sends keystrokes or tasks, creates no listeners, and runs no business checks.
5. Report the first unchecked item, its owner, and its prerequisites; never present a more urgent later item as the next one, and never auto-dispatch just because a task is ready.

## Output and stopping

Give a briefing per the question; when runtime state is involved, include the executor name and workspace/tab/pane, observation time or recent activity, blockers, and the next action. A single factual question does not require the full template, and focus is not reported. If local writes occurred, briefly describe the changes and unverified items; apart from the automatic GC above, pure queries never reverse into acceptance or advancement flows. When the human owner wants a manual scan of the logbook, `bin/lb todo` can open the TODO.md human view (🚨/👱/next item/in progress) beside the logbook on first use; write commands auto-refresh it afterwards — see the [CLI reference](../../docs/lb-cli.md). For read-only todo filtering use `bin/lb task list`, and for the next item `bin/lb task next`; still verify scheduling semantics against the logbook source.
