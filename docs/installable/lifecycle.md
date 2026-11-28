# Logbook Lifecycle

The lb-* entries serve the same logbook. Follow the boundaries in the consuming repository's root `AGENTS.md`; shared definitions live in [Coordination](coordination.md), [Format](logbook-format.md), and [Configuration](configuration.md). Operation order is constrained by each skill's main file and its conditionally required references; not every request needs to traverse the full flow.

| Entry | Responsibility | Where it stops |
|---|---|---|
| [lb-plan](../../skills/lb-plan/SKILL.md) | Recover goals, organize tasks and coordinate design delivery and readiness | A reviewable plan or a precise gap; no dispatch |
| [lb-push](../../skills/lb-push/SKILL.md) | Verify current authorization, dispatch or resume, monitor, and handle execution blockers | End of authorization, a human gate, or a severe blocker; continuous serial progress within authorization |
| [lb-update](../../skills/lb-update/SKILL.md) | Refresh verified progress, or reread human edits to align understanding | Reread is read-only by default; updates need evidence; no dispatch |
| [lb-status](../../skills/lb-status/SKILL.md) | Observe logbooks and the authorized control plane, maintain a few status snippets | Status briefs and local diffs; does not change acceptance verdicts or control agents |
| [lb-preflight](../../skills/lb-preflight/SKILL.md) | Check the route, reported design readiness and applicable prerequisites | A machine-readable preflight record in Thinking and 🔮 pending-discussion blockers; no dispatch, no unblocking |

## Stages and Entries

lb-plan coordinates design delivery through tasks, dependencies and acceptance arrangements. Responsible parties use their own host design workflows and report pointers and conclusions. lb-preflight checks applicable readiness evidence and prerequisites. Ordinary execution and bounded POC execution both require a confirmed applicable route, ready preflight inputs and separate execution authorization. Ordinary execution requires applicable reported design readiness. A bounded POC may run before overall design readiness within its confirmed scope and stopping point. See the [coordination contract](coordination.md#design-state-and-execution-readiness). Returns and human close-out go through lb-update. lb-status remains available at any stage.

The lifecycle is not a chapter template for logbooks. Numbers like `Stage 01` follow the real project's delivery breakdown; do not mechanically write "plan, push, update, status". Reuse valid artifacts, and do not plan from scratch when taking over or recovering from a disconnect.

## Handoffs and Changes

- Goals, scope, dependencies, ownership, or acceptance criteria change: lb-plan states the impact and authorization, keeping unconfirmed proposals separate from the current path.
- lb-push starts ordinary work when its applicable route is confirmed, preflight inputs are ready, design readiness is reported and the work has its own execution authorization.
- lb-push may start a bounded POC before overall design readiness once its applicable route is confirmed, its preflight inputs are ready and POC execution is separately authorized. Honor the POC scope, dependencies and stopping point.
- A 🔮 pending-discussion item exists: the affected logbook stops advancing until a human adjudicates the blockers found by lb-preflight; it resumes after the human rewrites or removes the 🔮 in the logbook.
- The current work package is returned: within the same authorization, lb-push may use lb-update's verification flow; the human need not retype the skill name, and no separate acceptance rule set is created.
- Evidence is missing or implementation failed: lb-update records the gap on the original item. Inspection or rework already authorized within the original work package can continue via lb-push; new scope requires separate confirmation.
- The user only requests an update or status: do not automatically fall through into lb-push. A status query may maintain emoji and a few fact snippets within the logbook write boundaries, without changing checkboxes, acceptance verdicts, or resuming execution; when the user explicitly asks for read-only, no files are written.
- A split has been approved and closed: migrate stages, bindings, and write entries per the [split flow](../../skills/lb-plan/references/planning.md#split-and-close-out); after the relevant coordinator acknowledges, report back to the receiving logbook. The original logbook's closure, stage acceptance, and overall goal attainment are recorded separately, preserving facts about skips and unfinished work.
- All results and applicable human decisions are in: lb-update records project completion. Cancellations and abnormal terminations are recorded truthfully and must not masquerade as successful delivery; session cleanup follows the separately authorized runtime conventions.

Explicit authorization does not lapse on skill switches, nor does the scope of authorization widen because of them. A skill handoff passes only task identity, existing artifacts, evidence, and decisions — it does not recursively load the whole skill stack.

## State Layering

Design readiness uses existing route and evidence fields. Host records hold the design. Captain recovers coordination decisions from any permitted [direct dialogue](coordination.md#captain-mediated-admiralsailor-dialogue) before affected work resumes.

Keep four kinds of facts distinct: authorization, runtime, work package, and acceptance. Real tool state keeps its control-plane name; "work package returned" is a coordination judgment, not a new Herdr enum. `idle`, `done`, or `blocked` only trigger a verification pass-back; they never automatically change acceptance verdicts.

The project logbook is the sole scheduling authority; bound mind-forge Prompt/Thinking records hold sources, authorizations, proposals, and handoffs; live session details stay in the control plane. A handoff must at least link the project checklist item, the work package and this dispatch, the owner, the authorization basis, the candidate, and the evidence. Reuse existing identifiers; there is no need to bulk-number historical logbooks or build a second task database.

## Generalization Boundaries

The skill flows apply to outcomes such as code, reports, and environments; stages and evidence are chosen per actual project. Document backends and runtime adapters are parameters; authorization, identity, evidence, isolation, and human focus are not switchable options. mind-forge document maintenance and Herdr runtime adaptation ship with the kit today; the CLI also supports standalone Markdown inspection/migration; other runtimes are unimplemented and must not be claimed as automatically supported.

## Scoped execution-mode switching

An explicit Admiral instruction activates [lb-takeover](../../skills/lb-takeover/SKILL.md).
On authorized release, [lb-handback](../../skills/lb-handback/SKILL.md) verifies
receipt, readiness and ownership before normal Sailor execution resumes. Follow the [ownership protocol](coordination.md#scoped-takeover-and-execution-handoff);
status/update/preflight do not start mode switches. No new lifecycle enum is added.

## Current lifecycle and close-out operations

The [operations contract](lifecycle-operations.md) defines the compact CLI-generated status, lifecycle transitions in existing skills, accessible-delivery responsibility, run event/closeout CLI, workflow provenance and main-branch lb-retro. It supersedes older statements that page status is never created or that lifecycle has no persisted state. Existing human text and gates remain protected; legacy migration is explicit. A lifecycle is not runtime state or execution authorization.
