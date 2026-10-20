---
name: lb-update
version: 0.4.1-dev
description: "Use when the user asks to fetch current progress and update the logbook, or says they edited the logbook and asks the agent to reread it. Rereading aligns understanding without writing by default; progress updates align applicable Sailor returns before writing. Does not dispatch tasks, and never checks a box on a verbal completion claim alone; human goals may be transcribed verbatim, and scope or acceptance-design changes go to lb-plan. Managed logbooks use mind-forge."
---

Captain maintains the Logbook goal/route and coordination; Sailors normally execute business work. Authorized scoped Captain execution follows the [takeover and handoff contract](../../docs/installable/coordination.md#scoped-takeover-and-execution-handoff). Align the actual executor’s current result (task/package, result, conditions, outcome and gaps) before recording completion. Status/update-only requests start no business work or execution-mode switch.


# Verify and update the logbook

Choose the entry from the user's intent before choosing a write mode:

- **Refresh progress** ("update the current situation"): read the current logbook and available Sailor returns within the authorized scope, align their current result/conditions and reported outcomes, then write the supported progress. A request to update includes reading available evidence; it does not authorize new execution or an unbounded investigation.
- **Reread human edits** ("I changed the logbook"): read the current file and align your understanding of its goals, constraints, tasks, order, and acceptance criteria. Compare only against a reliable prior file or conversation snapshot. Without one, summarize the current state and say that the changes cannot be reconstructed. Identify affected plans, candidate identities and evidence. Preserve human edits, including human-authored completion decisions; distinguish those decisions from independently verified results. By default, stop after this read-only alignment: do not write the logbook, Thinking or bindings, run sync, install dependencies, or dispatch work.

For a mixed request, reread the human edits first, discard stale assumptions, then refresh only the requested progress against the current criteria. A changed goal or threshold can invalidate old evidence even when a new version_token is available. A reread acknowledges the current plan; redesigning it belongs to lb-plan. A plain status query belongs to lb-status.

For authorized writes, mode is format (document maintenance), progress (result updates), or close (recording project wrap-up). These modes are internal write operations, not substitutes for the two user intents. Any new completion conclusion must align an applicable executor result (Sailor return or attributed Captain takeover result); it cannot be smuggled through format mode.

## Direct execution results

Read the takeover checkpoint when present and attribute its checks to Captain.
Align that recorded result against the task criteria without starting new business
checks. Permitted self-checks can support completion; required independent review
still needs a Sailor return on the same candidate. Preserve used review rounds
and open gates. An update-only request never invokes takeover or handoff dispatch.

## Captain return-alignment boundary

For business review material, align the current result identity/revision, current task/conditions, Sailor's declared checks/outcomes, gaps and usable delivery entry. Do not rerun original business or format criteria under the name "alignment": do not parse and compare all candidate rows, recount tables/headers/feedback, recompute rendered width budgets or independently declare content/layout passed. Ask the owning Sailor to supply missing checks within existing execution authorization; an update-only request records the missing return without launching work. Captain may read the current entry/first view and check its identity/accessibility; that is not a substitute content verdict.

This boundary does not prohibit CAS reads, inspecting the protected Logbook diff, preserving human bytes during an authorized coordination edit, or calculating requested coordination metrics from recorded events.

## Inputs and prerequisites

Resolve linked rules relative to the real path of the document containing the link, including inside the installed `.lbkit` directory. A default file search can omit hidden directories; it is not evidence that a prerequisite is missing. Try the resolved path before reporting a missing contract.

Input is the logbook location and the requested intent. Refresh progress additionally uses available candidates, original evidence or an explicit human decision; a reread does not require a completion evidence package. Before starting you must read the [configuration contract](../../docs/installable/configuration.md) and resolve documents; before writing you must read the [logbook format](../../docs/installable/logbook-format.md) and the [document adapter workflow](references/document-adapters.md).

progress/close must also read the [acceptance and wrap-up workflow](references/verification.md). Without the required rules or evidence, do not change completion conclusions; missing content cannot be replaced by defaults.

Apply the [format](../../docs/installable/logbook-format.md) ownership rules: explicit human decisions may locally rewrite unfinished agent tasks; human first lines remain protected, with only actual review-start progress writable. Keep process details in Thinking and source pointers in the corresponding existing host records, not main-logbook artifact inventories.

## Required workflow

For a reread, follow step 1 and report the aligned understanding and affected assumptions. The remaining steps apply only to authorized writes. Missing write dependencies do not block reading the current file; do not create bindings or install mind-forge just to reread.

1. Follow the [CLI read workflow](references/document-adapters.md#cli-invocation-in-this-repository) to get the current logbook's `context --json`, re-read the source and the relevant items, and verify versions and the user's concurrent edits. If an item has changed or been deleted, first confirm the correspondence; never overwrite by stale position.
2. Determine mode and impact: format protects ordering, thresholds, dependencies, ownership, and completion semantics; changing a working directory's machine ownership or adding/removing entries is not typesetting — the user must maintain or confirm it; confirmed entries are displayed per the [working directory format](../../docs/installable/logbook-format.md#working-directories) spec. Scope or acceptance-design changes belong to lb-plan, not to typesetting. The Overview goal and any historical human-authored Stage goal are protected; explicitly supplied wording may be transcribed verbatim with its source in Thinking; existing heading text and numbering must not be rewritten, except stage-status emoji synced per the rules. The placement and wording of small status and fact fragments is left to the model, without per-fragment confirmation; large prose is written by the human — do not reorganize sections or rewrite whole pages.
3. progress/close aligns current executor results (Sailor returns or attributed Captain takeover checks) with each task, result/revision, inputs/conditions, acceptance outcome, delivery entry and gaps. Captain checks correspondence and control/readiness facts; new business observations, testing and concrete rechecking require an authorized execution flow; this update entry only aligns recorded outcomes. A missing, stale, failed, incomplete or unknown return cannot close a task. An update-only request dispatches no new checking. Choose identity by deliverable type; not every result requires a commit or PR.
4. Before writing completion state, align item by item with the current task conditions, candidate identity and applicable executor result. After a candidate or acceptance-semantics change, an old pass conclusion does not by default support the new task; a new token only proves the new file version was read, not that it was accepted. Without matching evidence, keep the incomplete state and state the gap; with sufficient evidence and existing authorization, complete the update directly without re-asking. An incomplete delivery step does not satisfy that step, but does not create unrelated gates.
5. close verifies final deliverables, deviations, open responsibilities, and human decisions. Record an existing applicable decision directly; without one, remain pending acceptance. Record cancellation as cancellation — never disguise it as success — and do not clean up processes.

Todo format constraints: keep a linear execution path; do not split an operation where one owner delivers one result — split into sequential tasks when the owner or the acceptance gate changes. Splitting an existing manifest requires a confirmed basis; never reshuffle under cover of a result update. A task is owned either by a human or by an agent, never both roles at once. Mark the responsible repository with `@仓库` at the end of the task text, before the responsibility-role emoji; preserve that order when writing back.

Handoff entries serve the human: link current usable results and necessary limitations. Intermediate reports, work packages and raw records do not automatically become artifact lines. Align the current Sailor return and host-owned delivery entry; keep human-owned items free of agent artifacts.
1. After applicable executor-result alignment passes, including any required independent Sailor review, change status with the CLI `task update --status x`; use `task artifact` for agent artifacts and `task note` for necessary brief facts under a task. Preview the diff at every step, use returned version_token for the next already-understood write; re-read on conflicts or semantic changes, and finish with `sync` and `check`. The main logbook keeps only status, real artifact locations, and necessary brief facts; verification details stay in Thinking and source references — do not add a body-level audit section. Do not add agent artifacts to human-owned items; format-only fixes do not change completion state. Handle local edits the script does not support via the document adapter workflow. Managed logbooks require mind-forge and its Prompt/Thinking bindings and any existing host source bindings. Missing mf blocks dependent writes, not authorized maintenance of skills or ordinary repository docs. Protect private feedback, and report check failures or unverified items. When the repository root has `lbkit-skills.json` and an accepted task this round used an "action prefix + skill chain" combination absent from the manifest, you may propose adding it in the report; after human confirmation, write it with `bin/lb skills add`.

Organizing the skill manifest (when the user asks):
- Plan source: `bin/lb skills extract --json` gives the `技能：` original text, the todo, completion state, and a back-reference to the work package.
- Actual source: `bin/lb skills usage [--since <date>] [--json]` lists skills actually invoked in Claude Code and Codex sessions, covering only sessions whose working directory falls inside a logbook-registered directory or this repository; match them to work packages and todos by time, working directory, and arguments.
- Actual usage wins: where plan and actual differ, record by actual usage; do not record incomplete todos; do not classify logbook-maintenance and coordination skills (lb-*, herdr, etc.) as business work.
- Register each entry by "work type": `name` names the work type semantically; `scope` is written as 「适用：…；不适用：…」 (applies-to / not-for), distinguished by the nature of the work — not replaced by action prefixes or repository names; `actions` lists only common action prefixes; skills used incidentally along a main skill chain with no todo of their own (post-implementation cleanup, progress checks, process notes) go into `companions`, each with a `when`; `description` gives the next coordinator background: prerequisites, how to run it, limits and what not to use, and the source logbook or work package.
- A skill chain may include skills that exist only inside a business repository (e.g. its `.claude/skills/`); scope it to that repository in `scope` and state the repository and skill path in `description`; the Sailor must run inside that repository to invoke it.
- Present the organized result as a table for human confirmation, then run `skills add` entry by entry.

## Delivery and stopping

For a reread, summarize the current understanding, verified differences (if a reliable baseline exists), and affected plans or evidence; state that no files were changed. For a refresh, summarize actual writes, their evidence, incomplete items and who owns the next one. Read available records within the authorized scope; when new execution or out-of-scope evidence gathering is needed, report the precise gap without dispatching it.

This entry point does not call lb-push in reverse, nor does it close agents or services. If it was invoked from an already-authorized execution flow, return the verification result and let that flow judge whether it is still within its authorization.
