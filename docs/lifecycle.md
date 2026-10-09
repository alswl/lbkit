# Logbook Lifecycle

The lb-* entries serve the same logbook. Follow the [repository boundaries](../AGENTS.md); shared definitions live in [Coordination](coordination.md), [Format](logbook-format.md), [Evidence](evidence.md), and [Configuration](configuration.md). Operation order is constrained by each skill's main file and its conditionally required references; not every request needs to traverse the full flow.

| Entry | Responsibility | Where it stops |
|---|---|---|
| [lb-plan](../skills/lb-plan/SKILL.md) | Verify human goals, clarify, design collaboration, split tasks, and check readiness | A reviewable plan or a precise gap; no dispatch |
| [lb-push](../skills/lb-push/SKILL.md) | Verify current authorization, dispatch or resume, monitor, and handle execution blockers | End of authorization, a human gate, or a severe blocker; continuous serial progress within authorization |
| [lb-update](../skills/lb-update/SKILL.md) | Verify evidence, maintain records, log human decisions, and close out projects | Grounded updates; no dispatch |
| [lb-status](../skills/lb-status/SKILL.md) | Observe logbooks and the authorized control plane, maintain a few status snippets | Status briefs and local diffs; does not change acceptance verdicts or control agents |
| [lb-preflight](../skills/lb-preflight/SKILL.md) | Full pre-run preflight: route planning and step-by-step read-only feasibility analysis | A machine-readable preflight report and 🔮 pending-discussion blockers; no dispatch, no unblocking |

## Stages and Entries

This repository only exposes the lb-* coordination entries; Spec Kit's spec and implementation flows are left to the project repository's executor agents. The `.specify/` material kept here is for design reference only — it is not an executable coordination flow, and its hooks are not run. lb-plan verifies human goals and drafts todos for confirmation; it does not ghostwrite large blocks of project prose. Execution is delegated through lb-push; returns and human close-out go through lb-update. lb-status can be used at any stage. A plan-quality check proves readiness, not delivered completion.

The lifecycle is not a chapter template for logbooks. Numbers like `Stage 01` follow the real project's delivery breakdown; do not mechanically write "plan, push, update, status". Reuse valid artifacts, and do not plan from scratch when taking over or recovering from a disconnect.

## Handoffs and Changes

- Goals, scope, dependencies, ownership, or acceptance criteria change: lb-plan states the impact and authorization, keeping unconfirmed proposals separate from the current path.
- Ready and this item is authorized: lb-push starts execution. A plan existing, having been shown, or having passed analysis does not by itself authorize the start.
- A 🔮 pending-discussion item exists: the whole logbook stops advancing until a human adjudicates the blockers found by lb-preflight; it resumes after the human rewrites or removes the 🔮 in the logbook.
- The current work package is returned: within the same authorization, lb-push may use lb-update's verification flow; the human need not retype the skill name, and no separate acceptance rule set is created.
- Evidence is missing or implementation failed: lb-update records the gap on the original item. Inspection or rework already authorized within the original work package can continue via lb-push; new scope requires separate confirmation.
- The user only requests an update or status: do not automatically fall through into lb-push. A status query may maintain emoji and a few fact snippets within the logbook write boundaries, without changing checkboxes, acceptance verdicts, or resuming execution; when the user explicitly asks for read-only, no files are written.
- A split has been approved and closed: migrate stages, bindings, and write entries per the [split flow](../skills/lb-plan/references/planning.md#拆分与收口); after the relevant coordinator acknowledges, report back to the receiving logbook. The original logbook's closure, stage acceptance, and overall goal attainment are recorded separately, preserving facts about skips and unfinished work.
- All results and applicable human decisions are in: lb-update records project completion. Cancellations and abnormal terminations are recorded truthfully and must not masquerade as successful delivery; session cleanup follows the separately authorized runtime conventions.

Explicit authorization does not lapse on skill switches, nor does the scope of authorization widen because of them. A skill handoff passes only task identity, existing artifacts, evidence, and decisions — it does not recursively load the whole skill stack.

## State Layering

Keep four kinds of facts distinct: authorization, runtime, work package, and acceptance. Real tool state keeps its control-plane name; "work package returned" is a coordination judgment, not a new Herdr enum. `idle`, `done`, or `blocked` only trigger a verification pass-back; they never automatically change acceptance verdicts.

The project logbook is the sole scheduling authority; companion records (thinking in mind-forge) hold sources, authorizations, proposals, and handoffs; live session details stay in the control plane. A handoff must at least link the project checklist item, the work package and this dispatch, the owner, the authorization basis, the candidate, and the evidence. Reuse existing identifiers; there is no need to bulk-number historical logbooks or build a second task database.

## Generalization Boundaries

The skill flows apply to outcomes such as code, reports, and environments; stages and evidence are chosen per actual project. Document backends and runtime adapters are parameters; authorization, identity, evidence, isolation, and human focus are not switchable options. Markdown / mind-forge document adaptation and Herdr runtime adaptation ship with the kit today; other runtimes are unimplemented and must not be claimed as automatically supported.
