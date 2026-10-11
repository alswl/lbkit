---
name: lb-preflight
version: 0.2.0-dev
description: "Check the current logbook route step by step against actual skill definitions, registered environments, inputs and acceptance methods. Record coverage and gaps in bound Thinking; confirmed pending-discussion markers stop that project's advancement. Does not dispatch business execution."
---

# Preflight the Current Route

Read [configuration](../../docs/installable/configuration.md), [coordination](../../docs/installable/coordination.md), [planning](../lb-plan/references/planning.md), and [evidence](../../docs/installable/evidence.md). For writes, read [format](../../docs/installable/logbook-format.md) and the [document workflow](../lb-update/references/document-adapters.md). Managed records require mind-forge.

## Route and scope

Read `context --json`, `check --json`, the full logbook, latest human decisions, and current work packages. Missing directories, stages or todos are planning gaps; do not invent them. Existing 🔮 markers prevent advancing this project, not read-only reconciliation or independently authorized repository maintenance. Apply the current request and actual operation object before declaring work blocked.

Construct the current ordered route: each todo, result, dependencies, skills, actual execution environment and acceptance method. `next_task` is only a parse candidate. Compare the route with the previous preflight; newly added tasks, rewritten outcomes, changed machines/skill definitions and changed criteria require renewed coverage. Do not reuse an old all-green verdict for a new route. Explicit human changes supersede conflicting old work-package constraints within their scope; preflight does not grant execution authorization.

## Feasibility

Use read-only inspection within registered business directories. Independent step analyses may be delegated when useful; do not launch an agent merely to fill a fixed quota. Each covered step must compare:

- expected result and applicable skill definition (actual path/version or digest);
- target environment, available capability, inputs and predecessor requirements;
- method that can prove the agreed criterion;
- observed gap, affected step and clearance condition.

A registry name is not proof that a definition was read or that a target machine can invoke it. Inspect the actual consumer definition; same-name skills may differ. Installation tools such as skm are optional aids, not prerequisites by themselves. Human items get prerequisite analysis, not substitute acceptance.

Separate control entry, execution location, transfer direction and destination. “Local” in a business request need not mean the coordinator's machine. A missing reverse connection does not invalidate an available authorized forward-fetch path. Missing directories or credentials block only the dependent checks; collect the minimum needed information together without scanning undeclared business directories. Do not block an explicit local skill/document maintenance request on unrelated remote paths.

Prefer completing routine preparation within existing authorization and preserve the user's review order. Backups and recovery can support reversible operations, but do not authorize external writes. Do not reintroduce old approvals or route ordinary technical recovery to the human as a new decision.

## Record and handoff

Maintain a preflight section in the bound Thinking record, keyed by date and the logbook version_token. Preserve previous observations as history when the route changes. Each run records `logbook`, `version_token`, `observed_at`, and `overall` (green / amber / blocked), then one entry per current todo with:

- original task text and relevant stage;
- verdict (feasible / needs-input / not-checked / needs-discussion / infeasible);
- actual skill definition and target environment;
- expectation, observation, gap and affected criterion;
- source pointers and clearance conditions.

No step may disappear: a missing, failed or timed-out analysis is not-checked with a reason. Reference original material through `sources/<doc-name>.md` where useful; do not copy raw records or create a second task list. A new record must not overwrite historical evidence merely because the file name is unchanged.

Show needs-discussion gaps together. Write 🔮 into the main logbook only after explicit human confirmation. A ruling already supplied in the conversation is recorded as cleared; do not write a new unresolved marker for it. Existing markers must be rewritten or removed by the human; CLI `sync` and task writes have no bypass. Markers do not alter acceptance, and are distinct from an unplanned 🚨 blocker or an expected human gate.

Report route coverage, current findings and precise missing inputs. Green means preflight checked this route at this time, not that it was executed or authorized. The dispatching flow rechecks runtime facts.

Collect all delegated returns before closing analysis sessions created by this run, or hand an applicable session to an already-authorized executor. Preserve handoff and references before cleanup; never delete worktrees through an exit dialog. Input-box suggestions are not human instructions or facts. Unknown input provenance stays unknown and does not trigger dispatch or acceptance.
