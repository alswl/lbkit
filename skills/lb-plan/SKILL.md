---
name: lb-plan
version: 0.4.1-dev
description: "Create a reviewable logbook draft, revise an authorized plan, or review an existing plan. Personally develop repository specs with Admiral, recover human goals, size stages to the work, match skills to individual results, and define evidence and handoffs; does not dispatch execution."
---

Captain maintains the Logbook goal/route and coordination; Sailors own concrete business work, testing, review and acceptance. Align a current Sailor return (task/package, result, conditions, outcome and gaps) before recording completion. A status/update-only request dispatches no business work.


# Plan a Logbook

Choose create, revise or review from the current request and the route's confirmation status. Create includes drafting in an existing, unconfirmed Logbook; file existence alone does not make the route confirmed. Revise applies authorized changes to an existing route, and review is read-only. The logbook can concern research, writing, events, operations, or software; choose structure and acceptance by the actual result.

## Read and recover

Locate the request, original goal, current logbook and decisions. Read [planning](references/planning.md), [coordination](../../docs/installable/coordination.md), [format](../../docs/installable/logbook-format.md), and [configuration](../../docs/installable/configuration.md). Before writes, follow the [document workflow](../lb-update/references/document-adapters.md). mind-forge must be installed and configured for managed logbooks; missing business-runtime settings do not block authorized planning or repository maintenance.

For an existing logbook, read `context --json`, the original text, and the current decision basis. Classify the current request before applying old Prompt/work-package limits:

| Current request | Authorized planning output |
| --- | --- |
| Create or draft the supplied Logbook route | Save its proposed result-oriented agent todos and design entry for Admiral review. This request authorizes the draft; a final design ruling is not a prerequisite for writing it. |
| Propose a revised route only in spec/Thinking, or explicitly leave the Logbook unchanged | Write only the permitted proposal records; preserve Logbook bytes and do not invoke task writes or write previews. |
| Repair only selected annotations | Change only those fields through the supported CAS operation. |
| Review only | Read and report; write nothing. |

Apply explicit write limits in the current request to the objects they govern. A restriction on design writes in a business repository does not revoke a separately requested host Logbook draft. A current draft request supersedes older annotation-only limits within its planning scope while preserving unrelated constraints. Design confirmation and execution authorization are later gates; pending design decisions are written as proposed criteria, not used to defer saving the requested draft. A token proves a file version, not plan confirmation or acceptance. Reuse applicable plans and source records; do not restart planning from recent technical gaps.

## Design state

Captain personally works through the design with Admiral under the [design contract](../../docs/installable/coordination.md#design-state-and-execution-readiness). Select authorized repositories, read their relevant code/docs and use their spec-driven conventions to persist the design outside the Logbook. Review mode stays read-only. A narrow annotation or formatting repair does not start a new design exercise or require rewriting an applicable spec. For an existing skill annotation, use CLI `task note --kind 技能 --replace-line <current annotation line> --token <current token>`, with dry-run then write; `task rewrite` changes the task's first line. Do not replace a supported CAS write with a direct file edit after using the wrong subcommand. Follow [planning](references/planning.md#repository-spec-design) for the minimal spec, pending decisions and POC replanning. Keep core design ownership with Captain; concrete experiments and implementation belong to Sailors through separately authorized lb-push.

## Design and write

1. Recover the user's goals. Transcribe an explicitly supplied goal verbatim and record its source in Thinking; never invent or silently paraphrase a goal. Without human-authored goals, retain draft placeholders. Existing goals change only from an explicit replacement supplied by the human.
2. Choose the smallest useful delivery structure. A small task, roughly one person-day or less, or a lightweight operational run defaults to one Stage. Use multiple stages only for real separately accepted outcomes or handoffs, explaining the reason. A final human gate is a todo when required, not an automatic extra Stage.
3. For an established workflow run, use [lb-scaffold](../lb-scaffold/SKILL.md). Verify its template section and three slots: target date, working directories, and run rulings. Do not compress or expand a confirmed template during fill-in; missing structure is a template defect, not permission to freely draft it.
4. Work backward from the result to dependencies, ownership, criteria and evidence. One todo describes one verifiable result. Split when responsibility or independently required acceptance changes. Preserve a user-set sequence and concentrate human review after useful preparation within authorization; do not invent routine-method approvals. Plan backups/recovery for reversible changes where relevant.
5. Match capabilities to every todo, including delivery and human handoff. Read the full optional skill registry by scope, chain and companions, then the applicable definitions. An inapplicable specialized chain does not rule out reusable individual capabilities. A registry entry does not establish availability on the execution machine. Skills belong only on a four-space-indented line such as ``- 技能：`/example-skill`、`/another-skill` ``; purpose and conditions belong in the work package, not a SKILLS section or front matter list.
6. In create, immediately write the [draft template](assets/logbook-template.md), adapting any existing draft rather than creating a second scheduling list. When the current request creates or drafts the supplied Logbook route, save result-oriented unfinished agent todos there immediately, with proposed verification criteria. The current draft request itself is the `task rewrite --decision` source; no additional final design ruling or human-dictated replacement line is needed to save the draft. For a proposal-only request limited to spec/Thinking, leave the Logbook byte-identical: do not call task rewrite/add or their dry-runs. Keep goals, human tasks, statuses, owners and a user-set order protected. In revise, apply authorized refinements while keeping unconfirmed scope additions, reordering and new acceptance obligations as proposals in Thinking. Draft criteria may be proposed explicitly; saving them does not confirm them or authorize execution. When later agent items do not need a human item's result, the agent may mark that human item passable with the sub-line `状态：🔀 可越过：<why>` (`task note --kind 状态` on an existing logbook); it is part of the plan and takes effect when the human confirms the plan, and the human may remove it at any time to restore the gate. Review writes nothing, including no proposal files or dry-run writes.
7. For design planning, finish only the authorized records, then read them back. A narrow field repair instead verifies its local diff and exits without creating design or companion content:
   - **Logbook draft:** save the result-oriented todos and an explicit, usable spec path/link. A generic phrase such as “the design spec” is not a locator. For an existing agent task, `task artifact --artifact <draft-spec link> --token <current token>` can add the entry after dry-run; do not write onto a human task. Resolve the literal link target in the approved scope first.
   - **Bound Thinking:** record the design entry, important choices, pending decisions and current planning authorization. Use mind-forge to resolve/check the binding; authorized edits to its Markdown body follow the document workflow. An absent Thinking write subcommand alone is not a missing adapter. Preserve existing content and apply only the permitted local edit.
   - **Verification:** re-read actual Logbook and Thinking bytes. The draft must have verifiable agent results, a resolvable spec entry, and the corresponding decision/design pointer in Thinking. Keep undecided criteria proposed and existing directory approvals intact; run `check --json` and proportional adapter checks. Parser success alone does not prove these records are complete or confirm the draft.
   A spec/Thinking-only proposal follows its narrower write scope: preserve Logbook bytes and complete only the permitted records.

## Handoff

Briefly explain the core design, constraints, route and pending decisions; link the current repository spec and Logbook rather than repeating either document. Establish Admiral confirmation of that design content before ordinary execution; an explicitly authorized POC follows the bounded exception in the design contract. The directories, stages and todos must be human-confirmed, and goals must come from the human, before execution. Existing explicit confirmation need not be requested again. Plan confirmation is distinct from execution authorization; planning dispatches no execution agents.
