---
name: lb-update
version: 0.1.0
description: Verify and update the project logbook against new evidence or confirmed decisions, handling format fixes, acceptance results, and human wrap-up. Does not dispatch tasks, and never checks a box on a verbal completion claim alone; goal changes are written by the human personally, and scope or acceptance-design changes go to lb-plan. Supports plain Markdown and configured document backends.
---

# Verify and update the logbook

mode is format (document maintenance), evidence (result updates), or close (recording project wrap-up). Any new completion conclusion must go through evidence verification; it cannot be smuggled through the format mode.

## Inputs and prerequisites

Input is the logbook location, the basis for this change, and candidates plus original evidence or an explicit human decision. Before starting you must read the [configuration contract](../../docs/configuration.md) and resolve documents; before writing you must read the [logbook format](../../docs/logbook-format.md) and the [document adapter workflow](references/document-adapters.md).

evidence/close must also read the [acceptance and wrap-up workflow](references/verification.md) and the [evidence model](../../docs/evidence.md). Without the required rules or evidence, do not change completion conclusions; missing content cannot be replaced by defaults.

The first line of an existing todo must never be rewritten, appended to, or trimmed — only update checkbox state per evidence. Under a task, add only minimal status, blocker, or artifact links; process notes, technical detail, and detailed evidence go into the corresponding Thinking. Never expand the first line or sub-items on format or acceptance grounds.

## Required workflow

1. Follow the [CLI read workflow](references/document-adapters.md#本仓-cli-调用) to get the current logbook's `context --json`, re-read the source and the relevant items, and verify versions and the user's concurrent edits. If an item has changed or been deleted, first confirm the correspondence; never overwrite by stale position.
2. Determine mode and impact: format protects ordering, thresholds, dependencies, ownership, and completion semantics; changing a working directory's machine ownership or adding/removing entries is not typesetting — the user must maintain or confirm it; confirmed entries are displayed per the [working directory format](../../docs/logbook-format.md#工作目录) spec. Scope or acceptance-design changes belong to lb-plan, not to typesetting. The 「目标：」 lines of the overview and each stage are written only by the human personally; existing heading text and numbering must not be rewritten, except stage-status emoji synced per the rules. The placement and wording of small status and fact fragments is left to the model, without per-fragment confirmation; large prose is written by the human — do not reorganize sections or rewrite whole pages.
3. evidence/close checks each gate against the acceptance reference: identity, original records, independent checks, and applicable merge or runtime evidence; then judge pass, fail, insufficient evidence, or pending human decision. Choose identity by deliverable type; not every result requires a commit or PR.
4. Before writing completion state, align item by item with the current task's acceptance criteria, the candidate identity, and the original records proving that candidate passed. After a candidate or acceptance-semantics change, an old pass conclusion does not by default support the new task; a new token only proves the new file version was read, not that it was accepted. Without matching evidence, keep the incomplete state and state the gap; with sufficient evidence and existing authorization, complete the update directly without re-asking. Unmerged means the merge result is not checked.
5. close verifies final deliverables, deviations, open responsibilities, and human decisions. Record an existing applicable decision directly; without one, remain pending acceptance. Record cancellation as cancellation — never disguise it as success — and do not clean up processes.

Todo format constraints: keep a linear execution path; do not split an operation where one owner delivers one result — split into sequential tasks when the owner or the acceptance gate changes. Splitting an existing manifest requires a confirmed basis; never reshuffle under cover of a result update. A task is owned either by a human or by an agent, never both roles at once. Mark the responsible repository with `@仓库` at the end of the task text, before the responsibility-role emoji; preserve that order when writing back.

Handoff artifact constraints: when an agent task produces a report, test entry point, evidence index, or reproduction instructions, write one minimal artifact path indented 4 spaces under that agent task item; never write directly into a human-owned task item — handoff information belongs to the previous execution stage. When the real location is missing or content identity cannot be confirmed, report the gap; never invent paths, "final versions", or artifact summaries. A file existing or an artifact line written successfully is not acceptance passed.
6. After evidence verification passes, change status with the CLI `task update --status x`; use `task artifact` for agent artifacts and `task note` for necessary brief facts under a task. Preview the diff at every step, re-fetch context/token after each write before the next step, and finish with `sync` and `check`. The main logbook keeps only status, real artifact locations, and necessary brief facts; verification detail such as SHAs and per-sample check records stays in the existing evidence files — do not add a body-level audit section. Do not add agent artifacts to human-owned items; format-only fixes do not change completion state. Handle local edits the script does not support via the document adapter workflow. Perform document writes and the corresponding checks per documents.adapter: markdown requires no prompt/thinking or mf; mind-forge maintains bindings per its mapping. Protect private feedback, and report check failures or unverified items. When the repository root has `lbkit-skills.json` and an accepted task this round used an "action prefix + skill chain" combination absent from the manifest, you may propose adding it in the report; after human confirmation, write it with `bin/lb skills add`.

Organizing the skill manifest (when the user asks):
- Plan source: `bin/lb skills extract --json` gives the `技能：` original text, the todo, completion state, and a back-reference to the work package.
- Actual source: `bin/lb skills usage [--since <date>] [--json]` lists skills actually invoked in Claude Code and Codex sessions, covering only sessions whose working directory falls inside a logbook-registered directory or this repository; match them to work packages and todos by time, working directory, and arguments.
- Actual usage wins: where plan and actual differ, record by actual usage; do not record incomplete todos; do not classify logbook-maintenance and coordination skills (lb-*, herdr, etc.) as business work.
- Register each entry by "work type": `name` names the work type semantically; `scope` is written as 「适用：…；不适用：…」 (applies-to / not-for), distinguished by the nature of the work — not replaced by action prefixes or repository names; `actions` lists only common action prefixes; skills used incidentally along a main skill chain with no todo of their own (post-implementation cleanup, progress checks, process notes) go into `companions`, each with a `when`; `description` gives the next coordinator background: prerequisites, how to run it, limits and what not to use, and the source logbook or work package.
- A skill chain may include skills that exist only inside a business repository (e.g. its `.claude/skills/`); scope it to that repository in `scope` and state the repository and skill path in `description`; the executor agent must run inside that repository to invoke it.
- Present the organized result as a table for human confirmation, then run `skills add` entry by entry.

## Delivery and stopping

Summarize the updates, the basis, incomplete items, and who owns the next one. When cross-repository evidence gathering or re-verification is needed, report what must be sent back; do not investigate or dispatch on your own.

This entry point does not call lb-push in reverse, nor does it close agents or services. If it was invoked from an already-authorized execution flow, return the verification result and let that flow judge whether it is still within its authorization.
