---
name: lb-status
version: 0.6.2-dev
description: "Read-only project and executor status, blockers and next work. Reports canonical tasks and attributable runtime observations without writes, cleanup, dispatch or changing ongoing authorization."
---

## Current Markdown and synchronization

For new runs, queries read current Markdown and show missing/stale/synced. Report
stale projection without writing sync-state. Show responsibility, immutable binding
and original result provenance where available; absent source is unknown. Use
agent monitoring context for pending events/answers. Empty targets/no_targets
means no current monitoring targets, not business completion or absent history.

# Read project status

## Purpose and inputs

Answer the current question from the designated Logbook and applicable recorded
or live observations. This entry is always read-only: no sync, task notes,
checkbox changes, GC, reset, cleanup, session creation or dispatch, even when the
user does not explicitly say read-only. Report stale summaries instead of fixing them.

Read the host rules, [configuration](../../docs/installable/configuration.md),
[document state](../../docs/installable/document-state.md), and
[observation workflow](references/observation.md) for live observations. Resolve
links from the real installed skill path. Missing write dependencies do not prevent
reading current facts. Ask only if the target cannot be uniquely located.

For a "current branch" query, use the host's explicit project/branch bindings to
locate the Logbook. A branch name alone is not proof of a binding. If several
Logbooks remain possible, report that ambiguity rather than choosing by name.

## Read and judge

Read `log context --json`, `log check --json`, current source and relevant returns.
Use lifecycle and canonical Task facts, not heading emoji or stale prose, to report
progress. Distinguish done, cancelled, blocked, pause and unknown; unknown/pause
items remain visible but are not schedulable. Hard dependencies and human gates
still govern the next action. Do not dispatch merely because work appears ready.

Use records only when requested. Otherwise inspect an identifiable executor
through authorized read-only Herdr observations when available. Distinguish live
observations from saved bindings; unavailable identity means unknown, not stopped.
Idle/done/exit does not mean Task completion, and delivery does not mean acceptance.
A single snapshot does not prove stagnation. Report context or quota findings only
when actually measured; they do not trigger cleanup or automatic session changes.

For confirmed Captain takeover/handoff, show `👨‍✈️ Captain`, its scope and pending
ownership. An emoji alone proves nothing. Task pause never proves its Sailor stopped.
Preserve all human content and mark uncertainty rather than inventing completion.

## Build an evidence-based briefing

An ordinary "status / 进展如何 / 做到哪了" asks for enough context to judge the
work. Default to a single-screen overview in the user's language, led by a
Stage → Tasks view. Prefer useful visuals, numeric tables, short-text tables,
then prose. Use short labels in tables and put explanations outside them. A
screen is the chat reading budget, not an A4 printing requirement; do not claim
to know the viewport or enforce a fixed line count when it is unavailable.

Use the following order for a broad overview. Combine or omit empty sections;
keep narrow questions narrow. Never require a particular number of Stages,
delivery type, role, renderer or human gate to make the layout work.

1. **Title and conclusion.** Use "<recorded role> · <project> overview" when the
   role is established; otherwise omit it. State the goal and current situation
   in one short sentence each. Include the actual check time and timezone, and
   identify older recorded sources without presenting them as live observations.
   Name the lifecycle and delivery boundary. Termination is not successful delivery.
2. **Progress and Stage → Tasks view.** For a reliably enumerated, non-terminated
   route, retain one overall bar with exact done/total, rounded percentage and a
   compact state breakdown. Count current delivery-stage Tasks once each using
   canonical effective states. Show human-owned unfinished Tasks as a labelled
   subset, not extra Tasks. In route order, show each Stage's short name, Task
   states or types, done/total and a marker for the applicable next action. Aggregate
   completed Tasks; expand current, paused and gated work only as useful. Include
   the legend for the symbols used. For large routes apply the folding rule below.
3. **Delivered results.** Use at most one short table with no more than five
   valuable results and their counts, versions or status; use fewer when warranted.
   Prefer direct current review links and candidate identity. Keep different units
   separate. Distinguish historical accepted results, current candidates and
   unaccepted snapshots, as well as preparation, implementation, self-test,
   independent verification and release when applicable. A completed investigation
   may establish a failure finding without making the investigated operation pass.
4. **Expose constraints and responsibility.** For each material blocker or open
   handoff, name the affected Task, owner, missing input and exact clearance condition.
   If ownership is unknown, say so and identify Captain's owner-resolution action.
   Distinguish human decisions, technical obstacles and ordinary remaining work;
   say which unknowns may remain under the existing acceptance criteria.
5. **Next actions by owner.** Link the applicable next Task using its freshly read
   Logbook line. Use a compact owner/action/deliverable table when comparing duties;
   distinguish Agent preparation from any actual human review or ruling. Name the
   material or version to review, allowed residual gaps and the condition for
   advancing. Do not hand Agent-owned preparation to the human or invent a human
   gate; if none applies, say "No human action is needed for this step". Present
   proposals and waiting conditions without implying dispatch or new authorization.
   For terminated routes, report no schedulable next Task, only existing open duties.
6. **Repository and check footer.** Compress relevant Git/PR and document diagnostics
   into one or two lines; apply the evidence limits below. Show missing/stale/synced
   projection, source conflicts and live-unknown when material. Do not hide a newer
   cancellation or decision behind historical counts or saved runtime facts.

The first unchecked Task is not automatically the next authorized action. Read
its conditions and current decisions: explicitly deferred or registration-only
work is not ready. Report any mismatch with CLI next-task suggestions without
rewriting the route. Advance past paused work only where the confirmed route
permits it and the next work's dependencies, human gates and authorization hold;
explain that exception instead of implying the paused work completed.

### Repository and diagnostic evidence

Use the selected Logbook's host repository, not the toolkit repository, for branch,
HEAD and working-tree facts. Report ahead/behind only against an existing local
tracking reference, with its freshness limitation; status never fetches to fill
the display. Inspect only relevant PRs through already authorized read-only tools.
If unavailable, label PR state and draft/WIP status unverified or recorded; do not
infer them from a link, completed Task or old merge report.

Separate deterministic structural errors from notices and unverified links using
the documented diagnostic codes, not just the check exit status. Count the returned
link occurrences and label that unit; do not imply they are unique URLs. Unknown
or unreadable check output is not zero errors. Missing fields may be omitted or
marked unknown; never repair records, fetch, broaden repository access or install
tools to complete the footer.

### Counting rules

- Prefer the public CLI's parsed current Tasks and effective states, cross-checked
  against current Markdown. Do not count annotations, Overview checklists, archived
  parents, code examples or old spec inventories as current Tasks. Do not guess
  ambiguous legacy markers; retain unknown and report the ambiguity.
- Use mutually exclusive primary state buckets so the counts reconcile to total.
  Blocked is the effective bucket for a pending/active Task with a current blocker;
  human ownership and execution observations are separate dimensions.
- Calculate **recorded Task completion = done / all current Tasks**, with
  exact numerator and denominator and at most a rounded whole percentage. Cancelled
  and not-applicable Tasks remain separate non-done buckets in that denominator.
  This is an item count, not an estimate of effort, time remaining or overall product
  delivery. Do not average stage percentages or invent weights. If another scope is
  requested, label the inclusion/exclusion rule explicitly.
- For terminated routes, foreground termination and label counts historical;
  suppress a completion-percentage bar that could imply ongoing delivery. Unchecked
  historical Tasks remain recorded unfinished, not automatically cancelled Tasks.
- With zero Tasks, show "0 recorded Tasks; completion ratio not applicable". With
  incomplete enumeration or unreadable state, show the known subset and unknown
  coverage; omit a percentage rather than treating missing data as zero.
- Report tests, elapsed time, first-pass acceptance, interactions or changes since
  the last report only when applicable evidence supports them. Keep passed, failed,
  skipped and NOT_RUN distinct. Use a comparable prior snapshot for a delta; without
  one, report current facts. No invented ETA, throughput or quota savings.

### Visuals inside agent chat

Render the briefing directly in the response; do not create a dashboard file,
companion checklist, server or monitoring session for a status question. Keep the
main view compact when presenting Stages or quantified comparisons:

- Retain the overall bar when its counting preconditions hold. The Stage → Tasks
  view adds the distribution and gates; a separate flow adds value only for real
  dependencies. Avoid multiple charts repeating the same counts. Add a per-stage
  bar only for a particularly useful comparison. Bars encode the labelled Task
  ratio with no partial credit for active work; exact numbers govern any rounding
  of the bar's cells. Pair symbols or colors with readable labels. ASCII is valid.
- Use Mermaid only when the chat host is confirmed to render it. Markdown support
  or a TTY does not establish that capability. In terminals or unknown hosts, use
  directly readable text; never deliver Mermaid source as the visualization.
- When an existing **beautiful-mermaid** renderer is available, prefer its rendered
  Unicode/ASCII output for terminal chat and its SVG output for hosts that can
  display images inline. This also works when the host cannot render Mermaid
  itself: feed source to the renderer and return the rendered output. See the
  [rendering notes](references/briefing.md#beautiful-mermaid-rendering). Do not
  install packages, add a consumer dependency or assume a local tool path exists
  merely for a status query; fall back to the text bar/table when unavailable.
- Keep tables narrow (for example Stage, done/total, remaining result). For many
  Stages, first compress each to one line; if that still exceeds the reading budget,
  show current and relevant neighbors plus an explicitly labelled remainder whose
  counts still reconcile. Preserve material blockers and human gates in the folded
  summary. On narrow screens use short per-stage lines rather than horizontal scroll.
- Connect nodes only for recorded dependencies; document order alone is not proof
  of a dependency. Keep the human gate and critical missing input visible.

See [the fictional chat example](references/briefing.md) for the expected level of
detail and a text-only fallback; adapt the shape to the evidence, not its numbers.

## Output and exit

Use verified current
Logbook line locators under the
[locator contract](../../docs/installable/coordination.md#human-facing-logbook-locators).
A requested checklist belongs in the response, not a new companion file.

A standalone query grants no execution authority. When called inside already
authorized work, return the observations to Captain; that calling flow answers
and actually continues the next authorized action. An ordinary status question
does not revoke authorization. Explicit pause/cancel/read-only steering still applies.
