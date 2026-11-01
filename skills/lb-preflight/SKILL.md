---
name: lb-preflight
version: 0.5.0-dev
description: "Check the current logbook route step by step against actual skill definitions, registered environments, inputs and acceptance methods. Record coverage and gaps in bound Thinking; confirmed pending-discussion markers stop that project's advancement. Does not dispatch business execution."
---

# Prepare the concrete next step

## Purpose and inputs

Take the saved route one concrete preparation step forward: inspect the actual
selected capability and obtain supported preview/dry-run findings. Inputs are
current Logbook/context, next Task, relevant design and existing authorization.
Preflight reports preparation; it does not grant execution authority.

Read the installed [configuration](../../docs/installable/configuration.md),
[coordination](../../docs/installable/coordination.md), and
[planning](../lb-plan/references/planning.md) contracts. Resolve relative links
from the real skill path. Read [document adapters](../lb-update/references/document-adapters.md)
and [state recovery](../../docs/installable/document-state.md) before writes.
A failed read is a specific gap; a guessed path is not evidence of absence.

## Scope and feasibility

Read the current source, `log context --json`, `log check --json`, relevant
specification and prior preparation. Select the actual next authorized step;
`next_task` is a parse candidate, not an authorization or business judgment.
Existing human gates remain binding. Unconfirmed design does not prohibit useful
read-only preparation, but green does not confirm design or authorize implementation.

Inspect only the selected step and its real dependencies. Compare expected result,
actual skill definition, inputs, execution location and verification method.
Distinguish control entry, source and destination; do not scan unrelated future
environments. Reuse unaffected findings. A changed route, skill, environment or
criterion invalidates the relevant preparation, not automatically the whole route.

Independent read-only analyses may be useful within existing authorization; there
is no fixed delegation quota. Gather any delegated findings before concluding.
Missing returns stay not checked. Business implementation or a real POC requires
its own authorized task and route, not a preflight label.

## Preview, prepare and replan

Use the selected capability's documented preview/dry-run on the concrete next
operation. Capture actual output and inspect changes/risks, including interruption,
replacement, missing prerequisites and recovery needs. A skill name or inferred
outcome is not a preview. If preview is unsupported, state that fact and the
available read-only evidence. Never perform an actual mutation to fake a preview.

Perform routine preparation within existing authority. Apply actual human limits
and review counting; do not invent a universal approval gate. For a material new
choice, ask a focused question with consequences. An unchanged obstacle becomes
an explicit blocker instead of endless identical retries.

Feed actual discrepancies back into lb-plan and save the revised affected route.
Then inspect the revised concrete next step. Built-in-only work is valid and needs
no invented skill label. Runtime prerequisites are separate from business evidence.
For Herdr, follow the current bundled skill and
[collaboration guidance](../lb-push/references/herdr.md); distinguish skill
installation/discovery, integration, session readiness and host completion delivery.
Provided setup records are controlled observations, not live environment checks.

## Output and exit

Save authorized findings in the bound Thinking with the relevant Task, observed
source/version, actual preview result, risks, gaps and next action. Preserve
historical evidence but do not duplicate the current Task list. Explicitly mark
uninspected future work as not checked; no blanket route-wide green from one preview.

Report ready / needs input / blocked for the inspected scope, with current
Logbook line locators and a link to details. Record a new 🔮 marker only on an
explicit human ruling; existing markers retain their human-only resolution rule.
No preview claim substitutes for design confirmation, human acceptance or execution
permission. Return to the authorized calling flow when preparation is sufficient.
