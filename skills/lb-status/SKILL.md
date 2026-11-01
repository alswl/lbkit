---
name: lb-status
version: 0.5.0-dev
description: "Read-only project and executor status, blockers and next work. Reports canonical tasks and attributable runtime observations without writes, cleanup, dispatch or changing ongoing authorization."
---

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

## Output and exit

Answer at the scale of the question: current progress, blockers, owner and next
step, plus observed runtime identity/time when relevant. Use verified current
Logbook line locators under the
[locator contract](../../docs/installable/coordination.md#human-facing-logbook-locators).
A requested checklist belongs in the response, not a new companion file.

A standalone query grants no execution authority. When called inside already
authorized work, return the observations to Captain; that calling flow answers
and actually continues the next authorized action. An ordinary status question
does not revoke authorization. Explicit pause/cancel/read-only steering still applies.
