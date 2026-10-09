---
name: lb-preflight
version: 0.1.0
description: Run a full end-to-end preflight against a logbook: parse the linear route in document order, dispatch a read-only analysis agent per step for feasibility analysis; write a machine-readable summary to sources/<main-log-name>-preflight.md; blockers pending discussion are written back to todos as 🔮 markers after human confirmation. While any 🔮 is unresolved the whole logbook must not advance, and bin/lb write commands are refused outright. Read-only preflight; does not dispatch execution.
---

# Logbook end-to-end preflight

This skill delivers preflight conclusions; it does not dispatch execution, write goals, or change the first line of existing todos. When a blocker is found, the only action is to mark it as a 🔮 pending-discussion item for human adjudication; the whole logbook stays frozen until a human clears the marker.

## Inputs and prerequisites

- Locate the single target logbook and run `context --json` and `check --json` (see [CLI read workflow](../lb-update/references/document-adapters.md#本仓-cli-调用)), then read the source. When `preflight_clear` is false, blockers already exist: first summarize the unresolved items for the human; do no new analysis this round.
- Read the [configuration contract](../../docs/configuration.md) to resolve this round's documents; read the [planning workflow](../lb-plan/references/planning.md), the [coordination contract](../../docs/coordination.md), and the [evidence model](../../docs/evidence.md). Before writing blockers back, read the [logbook format](../../docs/logbook-format.md) and the [document adapter workflow](../lb-update/references/document-adapters.md).
- A logbook missing any of the three essentials (working directories, stage breakdown, todo manifest) goes back to lb-plan to be completed; this skill neither writes goals nor adds todos on the human's behalf.

## Required workflow

1. Route planning: derive the linear path in document order — Stage → each todo → its skill chain / sub-items / artifacts and acceptance criteria → manual gates. `next_task` from `context` is only a parse candidate and must be verified against the source; for each step record the required outcome, predecessor dependencies, repositories and skills involved, whether inputs are present, and how acceptance is proven.
2. Step-by-step feasibility analysis (fan-out): dispatch one read-only analysis agent per step, constrained to the working directories registered in this logbook, and verify —
   - whether predecessor conditions hold and dependencies are valid;
   - whether the repositories / machines / environments a step references currently support it (read-only structural checks only; no business evidence gathered, no business commands run);
   - whether the skills and toolchains a step references actually exist and are invocable in the target environment (report a capability gap when they do not; do not substitute or downgrade); when `skm` is installed locally, `skm list --json` may help verify install status; missing skm is not a blocker;
   - provability of acceptance evidence: which numbers, environments, gates, or credentials are missing.
   Each step's expectations come from the skill that step references: the analysis agent should read that skill's definition (SKILL.md or the equivalent in the target repository) and output a comparison of "how the skill expects to work → what the repository/environment reality is → where the gap is", not settle for an inventory of "skill present / absent". Human-owned items only get their prerequisites analyzed.
   Analysis agents return in one round, reporting only facts and gaps — no iteration, no fixing, no artifact creation. When analyses of multiple steps are independent, dispatch them in parallel; this is read-only verification, not cross-item parallel execution. Concurrency follows current model service limits and host configuration; when limits are unknown, start with a small trial batch, and on rate limiting retry only the failed routes instead of rerunning the whole round. Where candidates allow, read-only analysis prefers a no-worktree setup; sensitive-handling rules still keep internal-only candidates as before.
3. Machine-readable summary: write conclusions into the owning project's `sources/<main-log-file-name>-preflight.md` (newly created, or an idempotent full-file overwrite; do not touch other records), with a fixed structure:
   - frontmatter: `logbook` (relative path of the main logbook), `preflight_date` (ISO date), `overall`: `green` (all feasible) / `amber` (has needs-input or not-checked) / `blocked` (has needs-discussion or infeasible);
   - **sections split by todo**: one H2 per todo (the todo's original text as the heading), each containing in order `verdict:`, skill chain, skill expectations, on-site reality, gap (reality vs expectation, item by item), blocker (`无` when none), evidence line numbers or paths; no sections unrelated to the todo;
   - list uncovered steps one by one with reasons; never silently drop steps. This file is an evidence index, not a second task list; detailed findings go into the corresponding thinking, not copied into the body.
4. Blocker write-back: for items whose verdict is `needs-discussion`, **first show the blocker list to the human in the conversation**; only after their explicit confirmation write the blockers back near the corresponding todos in the main logbook (prophecy-ball format: `- [ ] 🔮 待讨论：<one sentence> @<repo>`, or as an indented sub-item `- [ ] 🔮 …`). Blockers the human adjudicates and confirms on the spot in the conversation count as cleared once recorded in the preflight summary and thinking; no 🔮 write-back is needed. Write-back does not change goals, headings, or the first line of any todo, and checks no boxes; re-fetch `version_token` before writing and run `check --json` after. The write-back action itself is not subject to the existing 🔮 gate (the CLI only blocks sync/task write subcommands), but the same round must not use it to rewrite any existing task text either.
5. Closing report: show plan locations, the overall verdict, per-step conclusions, blocker line numbers, and clearance conditions; record in thinking the preflight date, coverage, unanalyzed items, and reasons. Conclusions are time-bound observations: all green only means "the pre-run preflight was not blocked"; runtime state is governed by the scene at lb-push dispatch time.

## Gate semantics (the contract with 🔮)

- 🔮 means "pending-discussion items found by preflight": they need human discussion and adjudication, and the whole logbook does not advance before adjudication. When any todo or its indented sub-items carries 🔮, `bin/lb` `sync`, `task update`, `task artifact`, `task add`, and `task note` all refuse with exit code 4; `context --json` reports `preflight_clear: false`, and `check` reports `PREFLIGHT_BLOCKER`.
- There is exactly one way to clear it: a human rewrites or removes the 🔮 by hand in the logbook (rewrites it into an ordinary todo, handles it separately, or deletes it); the CLI offers no bypass. The preflight skill itself also never rewrites the first line of a human todo.
- 🔮 does not change the acceptance semantics of the item it belongs to, nor is it 🚨 (an unplanned item requiring the human owner) or ⏳ (a reached human decision point); it refers specifically to pending-discussion blockers produced by preflight. The three are not interchangeable.

## Collection and wrap-up

- Collection: this skill's result is complete only after every analysis agent's conclusion has been retrieved (`herdr agent read` or the agent's on-disk path) and written into `sources/<main-log-name>-preflight.md`; any agent that fails to report, blocks, or times out is faithfully recorded in the preflight file as not-checked with the reason — never silently dropped.
- Before writing blockers back to the main logbook, first show the full blocker list to the human in the conversation and write only after their explicit confirmation; without confirmation no 🔮 is written to disk.
- When unsent user text is found in collected agent input lines, treat it as a user intent signal per repository rules: disclose it faithfully and act on the intent; do not ask the user to resend.
- Wrap-up: once all conclusions are collected, close every Herdr analysis tab created for this preflight round (`herdr tab close`, only tabs this skill created), leaving no analysis agents behind as idle sessions; take down monitors too, cleaning up only tabs this skill created. If lb-push immediately follows and reuses an analysis session as the executor, the corresponding tab is handed over as an execution tab and lb-push's wrap-up closes it.
- Residual worktrees from analysis agents started in worktree mode (e.g. `-w`): after read-only verification, hand them to the owning repository's executor agent or a human for deletion; the coordinator does not clean up across repositories.

## Boundaries

- Analysis agents are read-only and confined to registered working directories; data sensitivity follows the model and deployment rules of the [configuration contract](../../docs/configuration.md), and cross-repository input is handled at the strictest level.
- Capability gaps (missing skill, unreachable environment, missing credentials) are reported faithfully as needs-input; do not swap tools or downgrade on your own.
- This skill does not judge execution authorization itself; whether work is authorized is decided by what the logbook records and [AGENTS.md](../../AGENTS.md). Passing preflight authorizes no advancement; advancement still requires entering an approved lb-push.
