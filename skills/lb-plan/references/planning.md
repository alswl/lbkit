# Goal Recovery and Plan Design

Read for planning, takeover, or review. Read [coordination](../../../docs/installable/coordination.md) for authorization, [format](../../../docs/installable/logbook-format.md) for editable fields.

## Recover Goals and Decisions

Recover the original request, current human goals, latest explicit decisions, logbook and bound Prompt/Thinking. Do not substitute recent technical gaps for the mission. Human-provided goals may be transcribed verbatim with their source in Thinking; agent-inferred goals remain suggestions. New projects with missing goals remain drafts. Existing headings and goals are not rewritten for cosmetic reasons.

Apply a clear newer human ruling directly to the affected unfinished agent tasks and work packages. Do not let an old package's permissions override it, and do not expand unrelated scope. In review mode, output findings only: no files, proposal records or dispatch.

## Size and Template Selection

Derive stages from real separately delivered or accepted results. Small work (roughly one person-day or less) and lightweight operational runs default to one Stage; an applicable human gate is a todo, not a compulsory final Stage. Explain a multi-stage exception. Research, writing, events and environment work use their own criteria; no automatic code, release or merge steps.

A workflow run uses the template's 「运行实例模板」 section and exactly three mutable slots: target date, working directories, run rulings. Validate complete goal sentences, stage/todo structure and established human gates before fill-in. An object name cannot replace the target-date slot. A confirmed template is not freely compressed or extended by scaffold; missing slots require template maintenance, and an explicitly requested structural change belongs to planning.

## Capabilities and Work Packages

Read all optional `lbkit-skills.json` entries via `bin/lb skills --json`. Match by scope and outcome, not action-prefix keywords. Check the main chain and conditional companions against the target work. If a specialized chain does not apply, inspect reusable individual skill definitions rather than rejecting all capabilities or importing that chain's special requirements. Report registry gaps separately from missing capabilities; a missing chain entry does not block the main flow—cover build, delivery, installation, and human review from individual skills' own scope. Do not infer a skill's actual behavior from its name.

Cover result preparation, delivery, verification and human handoff where relevant. Resolve actual skill definitions in the environment that will execute them; record definition location and target-machine availability in preflight/work packages. Main todos only contain skill names on an indented `技能：` sub-line, with no purpose annotations or coordination adapters. Do not maintain a top-level or front matter skills inventory.

One concise todo names an action and verifiable result, retaining material scope and thresholds. Details and history belong in Thinking; source references may live in the corresponding `existing host records`. One owner delivering one result need not be fragmented into technical operations. Separate independently required responsibilities and gates; sequencing does not authorize parallelism.

Use the [work package](../assets/work-package.md) for the next authorized result; do not fully specify distant work prematurely. Record only applicable parameters. Independent checking must justify its value, use the same result identity and have finite rounds; no fixed agent count or mandatory checker for every task. A plan request does not launch agents.

Create writes a draft immediately, including placeholders and unconfirmed todos, for file-based review. Revise keeps undecided scope changes as proposals while applying explicit decisions locally. Preserve evidence correspondence when renaming unfinished agent todos with `task rewrite`; changed acceptance requires renewed verification. Human items retain their protected wording and terminal states.

## Split and Close Out

When the user explicitly asks to split an existing logbook, first confirm where phases go and which logbook closes out; implement explicit choices directly without re-requesting task authorization. A split migrates the current plan; it does not redesign goals or re-accept.

1. Read the source logbook, its bound prompts/thinking, referenced entry points, and the Captains currently maintaining the relevant phases. Divide along real sections; master-plan numbering does not imply a same-numbered Stage exists — do not fabricate missing sections.
2. Migrate approved phases verbatim: headings, goals, list order, ownership, task status, artifacts, and evidence. Verify item-by-item correspondence across the split — no dropped items, no duplicated executable lists, no turning skipped into passed; keep the original working directories and machine ownership.
3. In the original logbook, note the close-out scope and the follow-up entry point; in the new logbook, note the source, the inherited scope, and the original owner. Close-out only ends this logbook's scheduling; it does not mean the whole project meets its goals. Keep deviations, unfinished responsibilities, and human decisions; add no new gates or review rounds for the close-out.
4. Maintain existing bindings per the document adapter process. Keep and link historical ledgers; route new reports-back to the inheriting logbook; sync the old prompt's scope constraints too — it must not keep demanding maintenance of migrated phases. Do not ghostwrite original goals and completion criteria; state their cross-logbook applicability.
5. Re-read concurrent changes before writing; after writing, verify phase content, key links, and status are still intact, then run context/check on both logbooks. Never overwrite other Captains' new reports-back by saving a stale page wholesale.
6. Hand off old/new logbooks, companion records, responsibilities, and write entry points to the relevant Captains you are authorized to notify, and verify the actual main session received them. Without notification authorization, state who is pending handoff; never send messages on your own. Notification dispatches no business tasks and takes over no other phases. Report document migration completion and running Captains' receipt separately.

## Completion Checks

Item by item, confirm goal coverage, conflict-free dependencies, clear ownership, provable evidence, current work package completeness, valid parameters, and explicit authorization status. Separate observed facts, current goals, and unknowns. Finally present the plan location, paths, acceptance, and items awaiting human decisions; a file existing does not mean it was presented, and presentation does not mean execution is approved.

Before exit, confirm the three essentials — working directories, Stage division, and the todo list — are written into the logbook and manually confirmed by the user (the user writing or revising the plan personally counts as confirmation); plans short of confirmation must not enter lb-push execution.
