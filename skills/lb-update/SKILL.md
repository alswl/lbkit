---
name: lb-update
version: 0.5.0-dev
description: "Use when the user asks to fetch current progress and update the logbook, or says they edited the logbook and asks the agent to reread it. Rereading aligns understanding without writing by default; progress updates align applicable Sailor returns before writing. Does not dispatch tasks, and never checks a box on a verbal completion claim alone; human goals may be transcribed verbatim, and scope or acceptance-design changes go to lb-plan. Managed logbooks use mind-forge."
---

Read the [document state and CLI failure recovery contract](../../docs/installable/document-state.md).
If lb is unavailable or crashes, notify the user and take over safe authorized work;
report pending writes and verification gaps instead of silently stopping or bypassing CAS.
For an authorized refresh with no safe writer, the final reply must include the
contract's concrete pending change (task ID, current/proposed state, candidate,
evidence and applicable guarded operations), marked **not applied**. A fault
summary alone does not finish the refresh. Verify any cited source lines with a
numbered read; otherwise report the task without an unverified line number.


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

1. Follow the [CLI read workflow](references/document-adapters.md#cli-invocation-in-this-repository) to get the current logbook's `log context --json`, re-read the source and the relevant items, and verify versions and the user's concurrent edits. If an item has changed or been deleted, first confirm the correspondence; never overwrite by stale position.
2. Determine mode and impact: format protects ordering, thresholds, dependencies, ownership, and completion semantics; changing a working directory's machine ownership or adding/removing entries is not typesetting — the user must maintain or confirm it; confirmed entries are displayed per the [working directory format](../../docs/installable/logbook-format.md#working-directories) spec. Scope or acceptance-design changes belong to lb-plan, not to typesetting. The Overview goal and any historical human-authored Stage goal are protected; explicitly supplied wording may be transcribed verbatim with its source in Thinking; existing heading text and numbering must not be rewritten, except stage-status emoji synced per the rules. The placement and wording of small status and fact fragments is left to the model, without per-fragment confirmation; large prose is written by the human — do not reorganize sections or rewrite whole pages.
3. progress/close aligns current executor results (Sailor returns or attributed Captain takeover checks) with each task, result/revision, inputs/conditions, acceptance outcome, delivery entry and gaps. Captain checks correspondence and control/readiness facts; new business observations, testing and concrete rechecking require an authorized execution flow; this update entry only aligns recorded outcomes. A missing, stale, failed, incomplete or unknown return cannot close a task. An update-only request dispatches no new checking. Choose identity by deliverable type; not every result requires a commit or PR. For an observed interruption and return, record the attempt outcome with `dispatch attempt`, then separately record the dispatch as `returned` with `dispatch set-status`; a Thinking sentence does not replace either transition. These observations may be recorded while paused, without accepting the task or resuming execution.
4. Before writing completion state, align item by item with the current task conditions, candidate identity and applicable executor result. After a candidate or acceptance-semantics change, an old pass conclusion does not by default support the new task; a new token only proves the new file version was read, not that it was accepted. Without matching evidence, keep the incomplete state and state the gap; with sufficient evidence and existing authorization, complete the update directly without re-asking. An incomplete delivery step does not satisfy that step, but does not create unrelated gates.
5. For Stage/logbook close, run `lb log report --view closeout` with the adapter-resolved Thinking/run/scope under [lifecycle operations](../../docs/installable/lifecycle-operations.md). Align final deliverables, artifact-link observations, deviations, cleanup responsibilities, metrics and human decisions. Unknown historical metrics do not create a gate. For each required missing observation, the final reply must name the existing responsible role/repository, the evidence it must supply, and what will resolve the gap. Use recorded task ownership; when that owner is not identifiable, Captain owns resolving the assignment and reports it as unknown. Do not invent an assignee, dispatch work, or add a task merely to produce this handoff. Record cancellation as cancellation. Apply explicit pause/termination, reopening or evidence-based completion through `log state-set`; never hand-edit its status line or clean up processes here. Record attributed actual usage with `skill record-usage` for identified tasks: each invocation takes one usage object, not an array or a wrapper object. Prepare each input inside the approved root and use the returned Thinking token for the next record. Distinguish declared, invoked and observed outcomes; keep lessons in Thinking for lb-retro without adding project retro tasks.

Todo format constraints: keep a linear execution path; do not split an operation where one owner delivers one result — split into sequential tasks when the owner or the acceptance gate changes. Splitting an existing manifest requires a confirmed basis; never reshuffle under cover of a result update. A task is owned either by a human or by an agent, never both roles at once. Mark the responsible repository with `@REPO` at the end of the task text, before the responsibility-role emoji; preserve that order when writing back.

Handoff entries serve the human: link current usable results and necessary limitations. Intermediate reports, work packages and raw records do not automatically become artifact lines. Align the current Sailor return and host-owned delivery entry; keep human-owned items free of agent artifacts.
1. After applicable executor-result alignment passes, including any required independent Sailor review, for identified tasks use `task record-result` then `task accept --candidate ID` under the [domain command contract](../../docs/installable/domain-commands.md); only legacy unidentified tasks use `task update --status x`; use `task artifact` for agent artifacts and `task note` for necessary brief facts under a task. Preview the diff at every step, use returned version_token for the next already-understood write; re-read on conflicts or semantic changes, and finish with `log sync` and `log check`. Replace stale current status instead of appending routine history. Keep actual artifact entries in the Logbook and significant decisions/evidence in Thinking; do not add a body-level audit section. Do not add agent artifacts to human-owned items; format-only fixes do not change completion state. Handle local edits the script does not support via the document adapter workflow. Managed logbooks require mind-forge and its Prompt/Thinking bindings and any existing host source bindings. Missing mf blocks dependent writes, not authorized maintenance of skills or ordinary repository docs. Protect private feedback, and report check failures or unverified items. When the repository root has `lbkit-skills.yaml` and an accepted task this round used a work-type skill combination absent from available recipes, you may propose adding it in the report; after human confirmation, create a draft with `bin/lb config recipe create ID --input-file FILE --expect-version TOKEN --dry-run`, inspect and apply it, then use `recipe set-status` only when approval covers availability.

Organizing recipes (only when requested): compare `bin/lb skill extract` with
attributed `skill usage` records. Keep actual usage in Thinking; a recipe is a
reusable definition, not proof of adoption. Present the proposed `applies_to`,
`excludes`, `steps` and conditional `companions` for human confirmation. Apply an
approved definition through `config recipe create/update` with a current token and
preview; approval of a draft does not imply approval to make it available.
Business-repository skills keep explicit repository/path prerequisites in the
description; incidental skills belong in conditional companions.

## User-facing line guidance

Apply the [locator guidance](../../docs/installable/coordination.md#human-facing-logbook-locators) when reporting reread findings, written changes, incomplete items or decisions needed. Give the affected task/annotation and current `L50` position; after writes use the resulting file, not preview or old-file positions. Cite old positions only as explicitly labeled history when a reliable baseline exists. For a deleted item, identify its text and a verified surviving heading/neighbor when useful, without presenting the old line as current.

## Delivery and stopping

For a reread, summarize the current understanding, verified differences (if a reliable baseline exists), and affected plans or evidence; state that no files were changed. For a refresh, summarize actual writes, their evidence, incomplete items and who owns the next one. Read available records within the authorized scope; when new execution or out-of-scope evidence gathering is needed, report the precise gap without dispatching it.

This entry point does not call lb-push in reverse, nor does it close agents or services. If it was invoked from an already-authorized execution flow, return the verification result and let that flow judge whether it is still within its authorization.
