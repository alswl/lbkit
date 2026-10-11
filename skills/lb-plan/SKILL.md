---
name: lb-plan
version: 0.3.0-dev
description: "Create a reviewable logbook draft, revise an authorized plan, or review an existing plan. Recover human goals, size stages to the work, match skills to individual results, and define evidence and handoffs; does not dispatch execution."
---

# Plan a Logbook

Use create for a new draft, revise for an existing plan, and review for read-only analysis. The logbook can concern research, writing, events, operations, or software; choose structure and acceptance by the actual result.

## Read and recover

Locate the request, original goal, current logbook and decisions. Read [planning](references/planning.md), [coordination](../../docs/installable/coordination.md), [format](../../docs/installable/logbook-format.md), and [configuration](../../docs/installable/configuration.md). Before writes, follow the [document workflow](../lb-update/references/document-adapters.md). mind-forge must be installed and configured for managed logbooks; missing business-runtime settings do not block authorized planning or repository maintenance.

For an existing logbook, read `context --json`, the original text, and the current decision basis. A token proves a file version, not plan confirmation or acceptance. Reuse applicable plans and source records; do not restart planning from recent technical gaps.

## Design and write

1. Recover the user's goals. Transcribe an explicitly supplied goal verbatim and record its source in Thinking; never invent or silently paraphrase a goal. Without human-authored goals, retain draft placeholders. Existing goals change only from an explicit replacement supplied by the human.
2. Choose the smallest useful delivery structure. A small task, roughly one person-day or less, or a lightweight operational run defaults to one Stage. Use multiple stages only for real separately accepted outcomes or handoffs, explaining the reason. A final human gate is a todo when required, not an automatic extra Stage.
3. For an established workflow run, use [lb-scaffold](../lb-scaffold/SKILL.md). Verify its template section and three slots: target date, working directories, and run rulings. Do not compress or expand a confirmed template during fill-in; missing structure is a template defect, not permission to freely draft it.
4. Work backward from the result to dependencies, ownership, criteria and evidence. One todo describes one verifiable result. Split when responsibility or independently required acceptance changes. Preserve a user-set sequence and concentrate human review after useful preparation within authorization; do not invent routine-method approvals. Plan backups/recovery for reversible changes where relevant.
5. Match capabilities to every todo, including delivery and human handoff. Read the full optional skill registry by scope, chain and companions, then the applicable definitions. An inapplicable specialized chain does not rule out reusable individual capabilities. A registry entry does not establish availability on the execution machine. Skills belong only on a four-space-indented `- 技能：name、name` line; purpose and conditions belong in the work package, not a SKILLS section or front matter list.
6. In create, immediately write the [draft template](assets/logbook-template.md), adapted to the actual project, with todos and placeholders. Do not ask for permission to save the draft. In revise, apply explicit human decisions locally; keep unconfirmed scope/order proposals in Thinking, separate from the confirmed route. Use CLI `task add` for confirmed additions and `task rewrite` for authorized unfinished agent-task text changes. Human task wording stays protected. When later agent items do not need a human item's result, the agent may mark that human item passable with the sub-line `状态：🔀 可越过：<why>` (`task note --kind 状态` on an existing logbook); it is part of the plan and takes effect when the human confirms the plan, and the human may remove it at any time to restore the gate. Review writes nothing, including no proposal files or dry-run writes.
7. Maintain mind-forge bindings and, when needed, one [source reference index](assets/source-index.md) per document. Run `check --json` and inspect the diff. Check goal coverage, dependencies, working-directory ownership, current work-package inputs, evidence, and open decisions. Checks passing does not confirm the draft.

## Handoff

Report the file location, important choices and unresolved decisions rather than repeating the draft in chat. The directories, stages and todos must be human-confirmed, and goals must come from the human, before execution. Existing explicit confirmation need not be requested again. Plan confirmation is distinct from execution authorization; planning dispatches no execution agents.
