---
name: lb-plan
version: 0.6.0-dev
description: "Create, revise or review a Logbook route. Use for adding/removing/splitting Tasks, changing outcomes, order, dependencies, planned responsibility, skill chains, goals, design or acceptance criteria, including route changes requested through lb-update. Personally develop repository specs with Admiral; does not dispatch execution."
---

Read the [document state contract](../../docs/installable/document-state.md),
[configuration](../../docs/installable/configuration.md),
[planning reference](references/planning.md), and
[document workflow](../lb-update/references/document-adapters.md) as applicable.

# Plan a Logbook

## Purpose and inputs

Turn the human goal, current Logbook and applicable decisions into a saved,
reviewable route. Captain owns planning and Logbook changes. Choose create,
revise or read-only review from the current request. Existing file presence is
not confirmation, and a context token is not authorization.

Only lb-plan changes the route. lb-update records facts, applicable results and
the state of existing Tasks, including pause/resume and actual blockers, while
preserving that route. For a mixed request, apply the authorized planning changes
first, read back the saved route, then compose lb-update for the requested progress.
Reuse explicit decisions; a skill boundary adds no confirmation round. Rereading
human changes alone acknowledges the saved route without creating a planning write.

Read the host AGENTS.md, current source and `log context --json`. Recover the
human goal and current constraints; preserve human-authored wording and decisions.
A draft request authorizes saving proposed unfinished agent work. A proposal-only
request restricted to spec/Thinking leaves Logbook bytes unchanged. Review writes
nothing. Current instructions supersede older limits only within their scope.

## Build and save the route

1. Select or create one Logbook. Work initialization identifies its goal,
   constraints and next planning step; installing lbkit alone is not initialization.
   Compose lb-scaffold for an applicable confirmed template, otherwise use the
   existing draft template. Preserve confirmed template structure and human gates.
2. Work backward from the requested outcome. Use the smallest useful stages and
   result-oriented Tasks, with explicit dependencies and proportionate checks.
   Add an independent reviewer only when the actual work contract requires one.
   Preserve the user's order, environments, review allowance and approved scope.
3. Read applicable skill definitions and reusable workflows. Consider general
   reusable capabilities when a specialized chain is unsuitable. Built-in-only
   work is valid; do not invent a skill or new approval to fill a field. Save
   selected skills on their Tasks, not only in reasoning or a registry list.
4. Develop necessary repository design with Admiral under the
   [design contract](../../docs/installable/coordination.md#design-state-and-execution-readiness).
   Reuse applicable specs and confirmations. Save concrete design links and open
   choices in the authorized records; a narrow field repair needs no new design.
5. Save the authorized route through supported CLI operations with current CAS.
   Use `task note --replace-line` for existing annotations. For an authorized
   replacement, use atomic `task split` with the required reference mapping.
   Do not turn a proposal into execution or copy current Task state into Thinking.
6. Read back the final saved Task bytes: outcomes, dependencies, skill choices,
   human gates and design pointers must match the proposed route. Run applicable
   structural checks. Parser success alone does not establish semantic completeness.

## Judgment and exit

Return material unresolved decisions to the human with concise choices and
consequences. Use an available structured question mechanism; silence is not
consent. Routine authorized refinement needs no additional approval ceremony.

Hand the saved route and its concrete next step to lb-preflight. Its actual
preview findings may revise this route; retain unaffected preparation and inspect
only changed assumptions. Repeated unchanged obstacles need a focused question
or blocker, not another identical planning cycle.

Report saved outputs, relevant constraints, open decisions and the next step.
Use current Logbook line locators under the
[locator guidance](../../docs/installable/coordination.md#human-facing-logbook-locators).
Reuse explicit confirmation already supplied; planning itself dispatches no work.
