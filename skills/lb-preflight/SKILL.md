---
name: lb-preflight
version: 0.6.1-dev
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
For routine preparation, check the capabilities needed by the next step and reuse
applicable verified setup evidence while its runtime and host assumptions hold.
Keep foreground completion and post-turn automatic wake distinct. On first adoption
or a relevant capability change, validate the affected path using the
[host waiting contract](../../docs/installable/lb-cli.md#host-waiting-and-recovery).
Full host acceptance is not a prerequisite for work using an already verified path.
Provided setup records are controlled observations, not live environment checks.


For coordinated waiting, verify managed Observation setup and stable document/native
bindings. Claude Code prefers native Monitor with managed wait --stream when
available; foreground wait is the fallback. Check context recovery and Event
handling. Automatic answering may report capability_unavailable; prompt/send-keys
cannot replace native question confirmation. Follow [the wait contract](../../docs/installable/lb-cli.md#agent-wait-and-event-handling).

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

Read the saved todo list, the applicable workflow and registry, and the actual
primary and companion skill definitions. Compare each applicable skill with the
saved Skills sub-line, including skills for newly added and close-out tasks.
For each missing annotation, show the exact task and skill, even if Thinking
already mentions it. Record built-in-only work as such when its needs are
covered by built-in capability. When authorized to repair a missing annotation,
use `lb task note`, run `lb log sync-state` on the Logbook, and read back the
saved todo and annotation before refreshing the affected observation.

Report these findings for the selected step:

- **Test selection.** Record a module-level preview if available. Then use the
  test runner's exact selectors to collect the planned cases. Give the exact
  selectors, observed count and copyable rerun command with the working
  directory. Record discovery and actual run status separately. If selection
  remains open, give the missing input or unsupported capability.
- **Candidate readiness.** Identify the pinned candidate and test version, the
  checked environment, tools and input, and the available build, log, cache
  and acceptance paths. Mark each check as verified, missing, unverified or
  unnecessary for this step. Cite actual run output when execution occurred.
- **Delegation handoff.** When delegating, verify the current recipient, the
  authorized transfer scope, the execution environment and the approved model.
  If the actual model is observable only after launch, record the approved
  deployment and verify the actual model after launch. Recheck identity,
  authorization and CLI build identity on seat change, even when existing handoff
  evidence still applies on the same machine.

For each blocking observation, report the affected step, prerequisite, evidence,
responsible owner and clearance condition. State what the user needs to do now
or that the technical owner can proceed under existing authorization. When a
decision is required, give the choices, impact and latest deciding step.

Before adopting action-specific observations on a shared run, read back the
CLI version and implementation digest from `--build-identity` on each
actual participating launcher. Use `action: dispatch`
for delegation-only handoff gaps and `action: takeover` for Captain-only gaps.
Omit `action` for shared evidence. Record the checked versions or version gap,
the test rerun command and any actual first action as distinct evidence. If
delegation is blocked and Captain execution is authorized, check takeover
readiness with the actual Captain identity and its own execution conditions.

Record task readiness in the bound Thinking document with
`lb log record-readiness LOG --thinking PATH --input-file FILE --dry-run --json`.
Review the proposed update before applying. Carry forward the recorded history
and cite the actual source of each observation. Where a check depends on
workspace files, record their digests. Mark unverified external conditions as
unverified. After applying, synchronize Thinking explicitly and read back the
current outcome. See [the CLI contract](../../docs/installable/lb-cli.md#route-confirmation-and-task-readiness).
