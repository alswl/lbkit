# Goal Recovery and Plan Design

Read when planning, taking over, or doing a read-only review. Current repository constraints come from [AGENTS.md](../../../AGENTS.md); this file grants no additional investigation or execution authority.

## Recover Goals

First read the current request, the original task, the first assignment, the existing logbook, and the basis for decisions; prefer explicit human goals. Do not infer a mission from the latest CI gaps, technical debt, or active processes.

The overview's and each phase's 「目标：」 are authored by the human personally; the agent only verifies, points out gaps or conflicts, and proposes reviewable suggestions — it never writes suggestions into logbook goals. The wording and numbering of existing headings at every level are also human-maintained; status sync may only swap the emoji before a phase heading.

When something is missing or conflicting, use existing authorization to check original prompts and session facts with the relevant agents; no fixed headcount is required, and never launch agents just to fill a quota. If final deliverables substantively conflict, describe the conflict and hand it to the human to adjudicate — do not stitch them into a broad project.

Newly discovered issues become acceptance gates only when explicitly added to goals; otherwise treat them as evidence, risks, or pending decisions. Before investigating, verify existing authorization and let the execution entry point delegate within it; consult the human for out-of-scope information or investigation, and do not re-request already-granted authorization.

## Adapt to Project Type

Work backward from the final deliverable to phases, dependencies, and proof methods; no fixed industry or tech stack:

- Code changes: link the business repository's specs, fixed candidates, and applicable tests; list PR merge as an explicit todo only when merging is required, and do not let an implicit merge gate block completed phases.
- Reports or research: fix content versions, source and conclusion verification, and necessary human review; do not force deployment or code tests.
- Environment delivery: define environment identity, observation times, verification methods, and applicable rollback; runtime evidence does not prove permanent correctness.

Keep real workflow names and order; the phase count follows the deliverable. Do not convert existing numbered specs into fixed lifecycle headings. Projects with no release, publish, or rollback semantics do not get those steps; when release is required, design its work items, reviewers, credentials, and other prerequisite evidence in advance.

## Plan and Work Packages

The plan must make goals, non-goals, task ownership, dependencies, acceptance and evidence, applicable release rollback, and final decisions recoverable. Responsibility is made explicit by phase todos and work packages, with no separate "Participating Agents" section; the overview's `SKILLS` list only registers skills external to the repository and does not carry role assignment. Long-term details may be unknown; the package about to be dispatched must be complete. Use the [work package template](../assets/work-package.md) and record only the parameters and sources actually used this round.

When `lbkit-skills.json` exists at the repository root, draft a todo's `技能：` sub-line by first reading all entries via `bin/lb skills --json`; judge which kind of work the todo belongs to by each entry's `scope` (the work it covers and excludes); `actions` is only a hint — do not match mechanically by action prefix; on a hit, check the target repository against the `description` prerequisites; `companions` are skills used incidentally within the same todo per `when` — write them into the same `技能：` sub-line or the work package rather than splitting out separate todos. When the todo text alone cannot determine ownership (e.g. whether an item falls in a speckit tasks.md task range), read the corresponding work package, tasks.md, or thinking first; if still undetermined, leave it blank and note it in the draft. Submit it with the todo draft for human confirmation. The list is only an optional reference: without a list, or without a match, judge by the original rules; do not force-fill when nothing supports it.

Compress the main todo into one concise, verifiable sentence preserving the action, expected result, and non-omittable scope and acceptance thresholds; do not stuff background, operation history, past incidents, or multiple evidence paths into the sentence — move them to that item's indented sub-items or existing thinking. Compression must not erase authorization boundaries, dependencies, or acceptance conditions; operations by the same owner delivering the same result are not split; split into sequential tasks when the owner or acceptance gate changes, and do not parallelize on that basis.

Todo drafting has two paths: when `workflows/<workflow>/` provides a run-instance template, fill in the todo list, phase structure, goal template sentences, and adjudication defaults from the template item by item — no free drafting, no granularity changes, no adding or removing human gates; the confirmation rounds saved are the whole point of the template. Only without a template, or when goals/scope must change, use the generic drafting in this file. The two-line format, the `执行：` prefix, and the `🔀` batch convention follow the [Logbook Format](../../../docs/logbook-format.md); `🔀` decisions must check cross-repository read/write dependencies: across different repositories, one item reading and another writing the same file is likewise barred from concurrency.

For important deliverables, set an independent checker when feasible; the check scope, pass criteria, and finite round count must be explicit. When review is needed but rounds are not yet configured, propose a task-appropriate cap and confirm it in the work package; null must not be treated as an infinite loop. When no independent check is needed, state the rationale; do not invent tasks just to fill configuration.

Recommend adding an agent only when independent work, a different repository or specialized context, independent review, or an actual bottleneck justifies the coordination cost; attach name, scope, dependencies, and completion criteria. Do not launch it yourself.

Large prose bodies are written by the human; the agent must not ghostwrite them on the grounds that "the plan is approved". Present todo drafts in conversation first and write them only after confirmation; terminology, SKILLS, authorized directories, and short facts may be maintained per the [Logbook Format](../../../docs/logbook-format.md).

Mark new projects clearly as drafts; while goals have not been authored by the human, keep only placeholders and never let a draft exit into execution. For existing projects, keep unconfirmed additions, reorderings, or scope changes in proposals instead of overwriting the confirmed path; even when the human approves goal or heading changes, the human personally rewrites the corresponding text. Read-only review only outputs problem locations, impact, and handling suggestions; it writes no proposal files and changes no lists.

## Split and Close Out

When the user explicitly asks to split an existing logbook, first confirm where phases go and which logbook closes out; implement explicit choices directly without re-requesting task authorization. A split migrates the current plan; it does not redesign goals or re-accept.

1. Read the source logbook, its bound prompts/thinking, referenced entry points, and the Captains currently maintaining the relevant phases. Divide along real sections; master-plan numbering does not imply a same-numbered Stage exists — do not fabricate missing sections.
2. Migrate approved phases verbatim: headings, goals, list order, ownership, task status, artifacts, and evidence. Verify item-by-item correspondence across the split — no dropped items, no duplicated executable lists, no turning skipped into passed; keep the original working directories and machine ownership.
3. In the original logbook, note the close-out scope and the follow-up entry point; in the new logbook, note the source, the inherited scope, and the original owner. Close-out only ends this logbook's scheduling; it does not mean the whole project meets its goals. Keep deviations, unfinished responsibilities, and human decisions; add no new gates or review rounds for the close-out.
4. Maintain bindings and indexes per the document adapter process. Keep and link historical ledgers; route new reports-back to the inheriting logbook; sync the old prompt's scope constraints too — it must not keep demanding maintenance of migrated phases. Do not ghostwrite original goals and completion criteria; state their cross-logbook applicability.
5. Re-read concurrent changes before writing; after writing, verify phase content, key links, and status are still intact, then run context/check on both logbooks. Never overwrite other Captains' new reports-back by saving a stale page wholesale.
6. Hand off old/new logbooks, companion records, responsibilities, and write entry points to the relevant Captains you are authorized to notify, and verify the actual main session received them. Without notification authorization, state who is pending handoff; never send messages on your own. Notification dispatches no business tasks and takes over no other phases. Report document migration completion and running Captains' receipt separately.

## Completion Checks

Item by item, confirm goal coverage, conflict-free dependencies, clear ownership, provable evidence, current work package completeness, valid parameters, and explicit authorization status. Separate observed facts, current goals, and unknowns. Finally present the plan location, paths, acceptance, and items awaiting human decisions; a file existing does not mean it was presented, and presentation does not mean execution is approved.

Before exit, confirm the three essentials — working directories, Stage division, and the todo list — are written into the logbook and manually confirmed by the user (the user writing or revising the plan personally counts as confirmation); plans short of confirmation must not enter lb-push execution.
