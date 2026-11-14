---
name: lb-update
version: 0.6.0-dev
description: "Use when the user asks to update current facts, progress or explicit state decisions in the existing Logbook, or asks to reread human edits. Preserve the route: task membership, outcomes, order, dependencies, planned responsibility, goals and acceptance criteria change only through lb-plan. Rereading is read-only by default; completion aligns applicable executor results. Does not dispatch work. Managed logbooks use mind-forge."
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


# Update the current situation

Record what has happened, the applicable result and current Task state within
the existing route. Only lb-plan changes that route: adding/removing/splitting
Tasks, rewriting their intended results, reordering, dependencies, planned owners
or repositories, selected skill chains, goals, design and acceptance criteria.
Changing the route requires planning even when Admiral supplies exact wording;
the decision authorizes the scoped lb-plan change without another confirmation.

Completion, pause/resume, block/unblock and explicitly authorized cancellation or
reopening describe the state of an existing Task. They preserve its identity,
intended result and route position. A blocker or a pause supplies no authority to
bypass dependencies, select an alternative route or transfer responsibility.

Choose the entry from the user's intent before choosing a write mode:

- **Refresh progress** ("update the current situation"): read the current logbook and available Sailor returns within the authorized scope, align their current result/conditions and reported outcomes, then write the supported progress. A request to update includes reading available evidence; it does not authorize new execution or an unbounded investigation.
- **Reread human edits** ("I changed the logbook"): read the current file and align your understanding of its goals, constraints, tasks, order, and acceptance criteria. Compare only against a reliable prior file or conversation snapshot. Without one, summarize the current state and say that the changes cannot be reconstructed. Identify affected plans, candidate identities and evidence. Preserve human edits, including human-authored completion decisions; distinguish those decisions from independently verified results. By default, stop after this read-only alignment: do not write the logbook, Thinking or bindings, run sync, install dependencies, or dispatch work.

Reread human edits first and discard stale assumptions. Already-saved human route changes remain authoritative; acknowledging them does not authorize further route edits. When the request also asks to change the route, compose lb-plan for that part, read back the resulting route and current token, then use lb-update for the requested progress against its current criteria. Reassess affected evidence; a new token alone does not establish applicability. Keep undecided route changes as proposals and update unaffected authorized facts when possible. A plain status query belongs to lb-status.

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

Before declaring supplied returns missing, inspect the explicitly bound inputs and list files in the authorized task directory without limiting discovery to Markdown or state files. Read relevant return files, including JSON; an empty saved usage store does not mean no executor returns were supplied. Do not widen the search to other repositories.

progress/close must also read the [acceptance and wrap-up workflow](references/verification.md). Without the required rules or evidence, do not change completion conclusions; missing content cannot be replaced by defaults.

Apply the [format](../../docs/installable/logbook-format.md) ownership rules. Task rewrites from explicit human decisions belong to lb-plan; human first lines remain protected, with only actual review-start progress writable. Keep process details in Thinking and source pointers in the corresponding existing host records, not main-logbook artifact inventories.

## Required workflow

For a reread, follow step 1 and report the aligned understanding and affected assumptions. The remaining steps apply only to authorized writes. Missing write dependencies do not block reading the current file; do not create bindings or install mind-forge just to reread.

1. Follow the [CLI read workflow](references/document-adapters.md#cli-invocation-in-this-repository) to get the current logbook's `log context --json`, re-read the source and the relevant items, and verify versions and the user's concurrent edits. If an item has changed or been deleted, first confirm the correspondence; never overwrite by stale position.
2. Determine mode and impact: format preserves the route and completion semantics. Route edits, including explicit new goal wording or working-directory ownership changes, go through lb-plan under their existing authorization. Preserve Overview/Stage goals, existing heading text and numbering; authorized stage-status emoji sync follows the rules. The placement and wording of small status and fact fragments is left to the model, without per-fragment confirmation; do not reorganize sections or rewrite whole pages.
3. progress/close aligns current executor results (Sailor returns or attributed Captain takeover checks) with each task, result/revision, inputs/conditions, acceptance outcome, delivery entry and gaps. Captain checks correspondence and control/readiness facts; new business observations, testing and concrete rechecking require an authorized execution flow; this update entry only aligns recorded outcomes. A missing, stale, failed, incomplete or unknown return cannot close a task. An update-only request dispatches no new checking. Choose identity by deliverable type; not every result requires a commit or PR. For an observed interruption and return, record the attempt outcome with `dispatch attempt`, then separately record the dispatch as `returned` with `dispatch set-status`; a Thinking sentence does not replace either transition. These observations may be recorded while paused, without accepting the task or resuming execution.
4. Before writing completion state, align item by item with the current task conditions, candidate identity and applicable executor result. After a candidate or acceptance-semantics change, an old pass conclusion does not by default support the new task; a new token only proves the new file version was read, not that it was accepted. Without matching evidence, keep the incomplete state and state the gap; with sufficient evidence and existing authorization, complete the update directly without re-asking. An incomplete delivery step does not satisfy that step, but does not create unrelated gates.
5. For Stage/logbook close, run `lb log report --view closeout` with the adapter-resolved Thinking/run/scope under [lifecycle operations](../../docs/installable/lifecycle-operations.md). Align final deliverables, artifact-link observations, deviations, cleanup responsibilities, metrics and human decisions. Unknown historical metrics do not create a gate. For each required missing observation, the final reply must name the existing responsible role/repository, the evidence it must supply, and what will resolve the gap. Use recorded task ownership; when that owner is not identifiable, Captain owns resolving the assignment and reports it as unknown. Do not invent an assignee, dispatch work, or add a task merely to produce this handoff. Record cancellation as cancellation. Apply explicit pause/termination, reopening or evidence-based completion through `log state-set`; never hand-edit its status line or clean up processes here. Record attributed actual usage with `skill record-usage` for identified tasks: each invocation takes one usage object, not an array or a wrapper object. Prepare each input inside the approved root and use the returned Thinking token for the next record. Distinguish declared, invoked and observed outcomes; keep lessons in Thinking for lb-retro without adding project retro tasks.

Preserve Task membership, order, dependency/skill annotations, responsible repository and role markers. A necessary split, new result, owner change or changed acceptance gate returns to lb-plan. Progress notes and artifact references do not rewrite the Task's result or introduce a new acceptance condition.

Handoff entries serve the human: link current usable results and necessary limitations. Intermediate reports, work packages and raw records do not automatically become artifact lines. Align the current Sailor return and host-owned delivery entry; keep human-owned items free of agent artifacts.
1. For an explicitly human-confirmed state change on a human-owned task, pass `--confirmed` on the semantic action (or unidentified `task update`), carrying the fresh token and confirmation basis. Without confirmation, retain the default ownership protection. This does not authorize a different content edit or bypass acceptance, dependencies or CAS; separately human-approved details use note/artifact with `--confirmed`, while route/criterion rewrites remain lb-plan work. After applicable executor-result alignment passes, including any required independent Sailor review, for identified simple tasks use `task complete` with a current token and basis; use `task record-result` then `task accept --candidate ID` only when the actual contract requires candidate-specific recorded acceptance under the [domain command contract](../../docs/installable/domain-commands.md); only legacy unidentified tasks use `task update --status x`; use `task artifact` for agent artifacts and `task note` for necessary brief facts under a task. Preview the diff at every step, use returned version_token for the next already-understood write; re-read on conflicts or semantic changes, and finish with `log check`. Run `log sync` only when the request also authorizes derived-summary/stage maintenance; a targeted Task change does not authorize creating or refreshing unrelated summary content. Replace stale current status instead of appending routine history. Keep actual artifact entries in the Logbook and significant decisions/evidence in Thinking; do not add a body-level audit section. Do not add unconfirmed agent artifacts to human-owned items; format-only fixes do not change completion state. Handle local edits the script does not support via the document adapter workflow. Managed logbooks require mind-forge and its Prompt/Thinking bindings and any existing host source bindings. Missing mf blocks dependent writes, not authorized maintenance of skills or ordinary repository docs. Protect private feedback, and report check failures or unverified items. Record actual skill usage with its true attribution. A recipe gap may be reported without changing the planned skill chain. Recipe-definition maintenance composes lb-init; changing a Task's selected skills composes lb-plan. Neither change is an implicit progress update.

## User-facing line guidance

Apply the [locator guidance](../../docs/installable/coordination.md#human-facing-logbook-locators) when reporting reread findings, written changes, incomplete items or decisions needed. Give the affected task/annotation and current `L50` position; after writes use the resulting file, not preview or old-file positions. Cite old positions only as explicitly labeled history when a reliable baseline exists. For a deleted item, identify its text and a verified surviving heading/neighbor when useful, without presenting the old line as current.

## Delivery and stopping

For a reread, summarize the current understanding, verified differences (if a reliable baseline exists), and affected plans or evidence; state that no files were changed. For a refresh, summarize actual writes, their evidence, incomplete items and who owns the next one. Read available records within the authorized scope; when new execution or out-of-scope evidence gathering is needed, report the precise gap without dispatching it.

This entry point does not call lb-push in reverse, nor does it close agents or services. If it was invoked from an already-authorized execution flow, return the verification result and let that flow judge whether it is still within its authorization.


## Dialogue-driven Task state

An explicit instruction to defer, resume or record another state of an existing Task
is authority for that scoped change. Resolve the target from current facts; ask
one focused question only if the task or a material decision is ambiguous. Use
available structured questions with concise choices; silence is never consent.

For legacy inline Resolution/Resume, preview and apply `task migrate` with the
current paired token before the authorized transition; stop on conflicting or
stale evidence. Keep short task IDs. Let the guarded writer store machine facts
in the owning mind’s `lb/` state, while decisions, reasons, dependencies, blockers
and evidence links remain readable. Never paste JSON into a task note. Cancellation
and reopen must retain historical reasons and evidence; read back both current
state and retained history.

Pause through `task pause`, then read back canonical state and scheduling. A
Status/Deferred note alone does not pause a Task. Resume through `task resume`,
preserving any underlying blocker; use an explicit destination only when prior
state is unknown. Use `task block/unblock` for actual obstacles, not ordinary
asynchronous waiting. These actions describe Task state, never proof a worker
stopped. Captain separately handles in-flight work and late replies within scope.

If the supported writer is unavailable, report the exact unapplied change without
claiming success. Do not substitute notes or duplicate sidecar state. A planned
reassignment or route replacement belongs to lb-plan; runtime acceptance alone
does not authorize changing the plan. Record actual receipt/acceptance under an
already-authorized assignment with its true attribution, without rewriting planned
responsibility or treating delivery/idle as acceptance. Captain owns all Logbook
writes; Sailor returns observations only.
