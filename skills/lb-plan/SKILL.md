---
name: lb-plan
version: 0.6.1-dev
description: "Create, revise or review a Logbook route. Use for adding/removing/splitting Tasks, changing outcomes, order, dependencies, planned responsibility, skill chains, goals, design dependencies or acceptance criteria, including route changes requested through lb-update. Coordinate design delivery and readiness using responsible-party reports. Does not dispatch execution."
---

## Initialize and synchronize new runs

After generating an authorized new Markdown Logbook, run log init-state LOG
--name NAME with explicit associated --document paths. Identify Tasks with stable
short IDs and run log sync-state. After an authorized plan edit batch, explicitly
sync-state again. Markdown is SSOT; document writes need no caller CAS. Preserve
runtime history when moving/deleting Tasks; new split IDs inherit no execution
permission. Do not migrate old sidecars or rewrite consumer configuration.

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

Read the host AGENTS.md, current Logbook, bound coordination records and
`log context LOG --no-link-content --json`. Use the same option for structural
`log check` calls. If the installed CLI lacks the option, use available
`log route` structure and the Logbook source. Use `log state` only on a build
known to skip local link content. Report the missing check coverage. Recover the
human goal and current constraints; preserve human-authored wording and decisions.
A draft request authorizes saving proposed unfinished agent work. A proposal-only
request restricted to an authorized coordination record leaves Logbook bytes
unchanged. Review mode reports findings without writing. Current instructions
supersede older limits only within their scope.

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
4. Coordinate design delivery under the
   [readiness contract](../../docs/installable/coordination.md#design-state-and-execution-readiness).
   Use the responsible party's pointers and reported status. Plan missing
   deliverables, leave unknown owners pending designation and show dependent work
   waiting for external conclusions. Route an explicit design request to the
   host's own workflow by naming the boundary and expected return in the reply.
   Do not open, author, edit, assess or choose a design, launch the host workflow,
   dispatch a design Task or declare a design done. Apply authorized route changes
   in mixed requests before handing applicable progress to lb-update.
5. Save the authorized route through supported CLI operations with current CAS.
   Use `task note --replace-line` for existing annotations. For an authorized
   replacement, use atomic `task split` with the required reference mapping.
   Do not turn a proposal into execution or copy current Task state into Thinking.
   Persist authorized prerequisites as Task dependencies, including a required
   human review before handoff. Use stable IDs for both Tasks, identifying any
   missing IDs first. Read the graph and current `route_ref` with
   `lb log route LOG --json`. Prefer the protected
   [dependency command](../../docs/installable/lb-cli.md#markdown-ssot-and-new-run-commands):
   preview and apply `lb task depends LOG --task-id ID --input-file FILE --expect-route ROUTE_REF`
   with the full intended `{"depends_on": ["ID"]}` list, retaining unaffected
   prerequisites. Use the current route reference for each edit. Review and
   proposal-only modes do not write Task IDs or dependencies.
6. Run `lb log route LOG --json` after saving. Check each changed Task by ID and
   compare its `dependencies` with the intended prerequisite IDs. An Overview
   note or Acceptance annotation does not create a dependency. If the graph
   differs, correct it under the existing authority or report the specific
   unsaved edge. Verify outcomes, skill choices, human gates and design pointers
   in the saved route and run applicable structural checks.

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

From the saved route readback, present the Stage order, deliverables, dependencies, owners, acceptance and human gates.
Record the human decision with its source and the reviewed route fingerprint.
