# Goal Recovery and Plan Design

Read for planning, takeover, or review. Read [coordination](../../../docs/installable/coordination.md) for authorization, [format](../../../docs/installable/logbook-format.md) for editable fields.

## Recover Goals and Decisions

Recover the original request, current human goals, latest explicit decisions, logbook and bound Prompt/Thinking. Do not substitute recent technical gaps for the mission. Human-provided goals may be transcribed verbatim with their source in Thinking; agent-inferred goals remain suggestions. New projects with missing goals remain drafts. Existing headings and goals are not rewritten for cosmetic reasons.

Apply a clear newer human ruling directly to the affected unfinished agent tasks and work packages. First distinguish which records the current request permits writing. A request to create or draft the supplied Logbook route authorizes saving proposed result-oriented agent-task wording without requiring a settled design or human-dictated replacement lines. Record that request as the task rewrite decision source; older annotation-only Prompt/work-package limits do not override it within the same scope. Directory write access does not expand planning into design work. A request limited to a Thinking route proposal authorizes neither Logbook rewrites nor POC insertion; preserve the confirmed Logbook byte-for-byte and discuss the proposed route in the permitted records. Preserve unrelated permissions, human task wording, goals, statuses, repository ownership and any user-set order. In review mode, output findings only: no files, proposal records or dispatch.

## Coordinate Design Delivery

Use only the responsible party's design pointer and reported review or
confirmation, including provenance and the scope it covers. Ask for missing
evidence or designation of an unknown owner. A missing required product or
technical design belongs in the proposed route as a delivery Task, such as
“Complete the product and technical designs and return their pointers and
review outcomes.” Capture distinct owners or acceptance gates separately when
applicable. Record dependent Tasks as waiting for the external conclusion.
Keep already approved repository access and established responsibilities.

An explicit request to produce, choose or review a design belongs to a
separately invoked host workflow. In a mixed request, save the authorized
coordination portion and explain the pending host handoff. Wait for its return.
On receipt, consume the attributed deliverable pointer, reported conclusion,
confirmation and affected scope. Apply only authorized scheduling changes and
use lb-update for authorized progress from the applicable return. A pointer or
a provisional report alone does not establish completion or readiness.

For a real POC, use the responsible party's reported question, scope,
dependencies, result criteria and stopping point. Propose the affected route
and obtain the applicable route decision before editing a confirmed route.
Keep proposal and scratch writes inside authorized directories. A POC needs
its own preflight and execution authorization through lb-push. Use the returned
judgment, boundaries, evidence and impact to coordinate follow-up, preserving
repository ownership and ordinary readiness gates.

## Size and Template Selection

Derive stages from real separately delivered or accepted results. Small work (roughly one person-day or less) and lightweight operational runs default to one Stage. When a revision introduces a distinct deliverable with its own acceptance, propose a separate Stage for that result and its gate. Keep completed task IDs, acceptance, and artifacts in their existing Stage. A human gate on the existing result stays in that result's Stage. Research, writing, events and environment work use their own criteria.

A workflow run uses the template's 「运行实例模板」 section and exactly three mutable slots: target date, working directories, run rulings. Validate complete goal sentences, stage/todo structure and established human gates before fill-in. An object name cannot replace the target-date slot. A confirmed template is not freely compressed or extended by scaffold; missing slots require template maintenance, and an explicitly requested structural change belongs to planning.

## Capabilities and Work Packages

Read approved recipes via `bin/lb config recipe list --status available --json`. Match `applies_to` and `excludes` against the intended outcome. Use `config recipe show ID` to pin its object digest in the work package; a recipe is guidance, not evidence that skills ran. Check the main chain and conditional companions against the target work. If a specialized chain does not apply, inspect reusable individual skill definitions rather than rejecting all capabilities or importing that chain's special requirements. Report registry gaps separately from missing capabilities; a missing chain entry does not block the main flow—cover build, delivery, installation, and human review from individual skills' own scope. Do not infer a skill's actual behavior from its name.

Cover result preparation, delivery, verification and human handoff where relevant. Resolve actual skill definitions in the environment that will execute them; record definition location and target-machine availability in preflight/work packages. Main todos only contain skill names on an indented `技能：` sub-line, with no purpose annotations or coordination adapters. Do not maintain a top-level or front matter skills inventory.

One concise todo names an action and verifiable result, retaining material scope and thresholds. Details and history belong in Thinking; source references may live in the corresponding `existing host records`. One owner delivering one result need not be fragmented into technical operations. Separate independently required responsibilities and gates; sequencing does not authorize parallelism.

Use the [work package](../assets/work-package.md) for the next authorized result; do not fully specify distant work prematurely. Record only applicable parameters. Independent checking must justify its value, use the same result identity and have finite rounds; no fixed agent count or mandatory checker for every task. A plan request does not launch agents.

Create writes a draft immediately, including in an existing unconfirmed Logbook, for file-based review. A confirmed directory or task order does not freeze all unfinished agent-task wording. When the current request authorizes writing the Logbook draft, turn action labels into a result and verification basis while preserving that scope and order; use `task rewrite` with the current request as the decision source. For example, “Implement adapter” becomes “Deliver an adapter conforming to the agreed interface, with valid-input and failure-case evidence.” If the interface or criterion is still undecided, identify it as proposed in the draft and link the relevant spec decision; do not invent agreement or a numerical threshold.

Revise keeps proposed scope additions, reordered dependencies and new acceptance obligations separate from the confirmed route. Preserve evidence correspondence when refining unfinished agent todos; changed acceptance requires renewed verification. Human items retain their protected wording and terminal states. For an authorized draft, verify the saved Logbook has verifiable todos and records the responsible party's actual design pointer when supplied. Record its attributed status and pending decisions in bound Thinking as authorized. Use the declared document workflow after resolving bindings. For a Thinking-only proposal, verify the Logbook remains byte-identical and avoid task writes and write previews.

## Split one task

When the human authorizes splitting one unfinished agent task, recover the replacement results, their order and repository assignments from that decision. Reuse the current route and original evidence. Missing decisions stay as proposals in the permitted records; a request limited to a proposal or review authorizes no Logbook write or write preview. Do not split human, completed or skipped tasks, or infer permission to transfer an existing repository.

A proposal-only reply names the replacement results in order, explains how the original task identity and evidence will be retained as provenance, and states that applying the split still needs authorization. Historical evidence does not accept a replacement. Keep this explanation in the requested reply when proposal files are not authorized.

Use `bin/lb task split LOG --stage STAGE --task ORIGINAL --into FIRST --into SECOND --decision SOURCE --expect-version TOKEN`, repeating `--into` for each approved replacement in order. For an identified original, use `--input-file` with `task_id`, replacement `{id,text}` entries and `reference_changes` for every dependent task; identify unidentified dependents first. Read current context and inspect the matching dry-run before the write. This single operation removes the original from the current list, preserves its complete content and provenance in the sidecar `task-archive`, and creates fresh `[ ]` replacements with their prerequisites. Do not compose separate retirement and insertion writes when the atomic operation is available; a partially completed sequence can lose or duplicate scheduling. If the installed CLI has no atomic split, report that specific gap and retain the plan rather than editing its body or leaving a partial migration.

After writing, read context and the saved diff: the original is absent from the current list and its complete content remains archived, replacements appear once in order with the approved repositories and prerequisites, and dependency mappings match the preview. Neither historical evidence nor an old acceptance state becomes new acceptance. Other task states, human input, goals and companion records stay intact. If a derived Stage marker needs syncing, use the new token for that operation's own preview and write. A split is a planning change and starts no business work. Existing owner responsibilities still require an applicable handoff before dispatching a replacement.

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

Ordinary execution also requires applicable reported design readiness under the coordination contract; an authorized POC has only its bounded exception. Before exit, confirm the three essentials — working directories, Stage division, and the todo list — are written into the logbook and manually confirmed by the user (the user writing or revising the plan personally counts as confirmation); plans short of confirmation must not enter lb-push execution.

After saving the route, use `lb log route LOG --json` to read back stage order,
tasks, dependencies and the reviewed scope. In the first Stage overview, show
the saved goal of each delivery stage beside its deliverables, owners,
acceptance criteria and human gates. Show the authorized directories and the
route or task scope the decision would cover. Keep directory line numbers as
locators. Record a genuine confirmation from its source, using the whole route
reference or the applicable task scope reference.

Reuse an applicable confirmation with the same fingerprint. If the fingerprint
changed, identify the affected scope. For a prior fingerprint, compare the
actual reviewed text and decision source with the current scope. With evidence
that the decision covers the current scope, use the authorized evidence update
to record that decision against the current reference. If the reviewed text or
coverage is unclear, ask for confirmation of the affected scope. Preserve the
original records and honor existing revocations.

Use the [route readiness CLI contract](../../../docs/installable/lb-cli.md#route-confirmation-and-task-readiness)
for the evidence format and protected update.
