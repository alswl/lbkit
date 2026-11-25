---
name: lb-preflight
version: 0.6.1-dev
description: "Check the current logbook route step by step against actual skill definitions, registered environments, inputs and acceptance methods. Record coverage and gaps in bound Thinking; confirmed pending-discussion markers stop that project's advancement. Does not dispatch business execution."
---

# Prepare the concrete next step

## Purpose and inputs

Prepare the next Task and the known prerequisites of the confirmed route.
Inputs are the current Logbook/context, relevant design, existing authorization,
and earlier preparation evidence.
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

Inspect the selected operation in detail. For each confirmed stage, inventory
the prerequisites that affect its Tasks: authorization, work locations, skills,
repository synchronization, authentication and assigned executors. Record
the affected Task, evidence, owner and clearance condition. Check only relevant
environments. If a prerequisite can be verified only later, name the step that
makes it verifiable and keep it pending. Reuse applicable evidence and repeat
checks only where their inputs or scope changed.

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

Perform and read back routine preparation across the confirmed route where
existing authority permits it. Compare the current setup with known working
configurations before asking for credentials or replacing a worktree. Preserve
uncommitted work and respect protected access and human limits. Continue other
authorized preparation when a prerequisite needs a human decision. Consolidate
new decisions and inputs with their effects on the affected Tasks.

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

For a managed Task, derive the complete self-check list from the confirmed route
and approved work package. Preserve each Sailor's Task, role, and check. Record
only the exact authorized list with `lb log preflight-plan`. Use an empty list
only when the confirmed scope calls for no Sailor checks. An unresolved
assignment or unreadable declaration leaves the affected checks unverified.
Use the assigned Sailor's current Binding when available. For preparation
before business binding, use an environment named in the approved declaration
and verify its machine, native session and work directory. A changed environment
requires current approval and a new check.

Use `lb agent self-check` for authorized preparation and
`lb log preflight-observe` to read back the actual reply. Match each reply to
the original operation, subject, current session, work directory and approved
candidate before using it. A submitted receipt or idle session establishes no
result. Reconcile unknown delivery before sending again. Keep valid results in
the temporary cache and repeat only affected checks after a session or scope
change. Report unsupported reply channels as unverified. Business dispatch and
Task ownership changes follow their normal authorized workflow.


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

Report ready, confirmed missing, unverified, or not applicable for applicable
prerequisites, with current Logbook line locators and a link to details. Give
the selected Task and the broader route their own readiness statements. Record
a new 🔮 marker only on an explicit human ruling and leave resolution of existing
markers to the human.

Include `🛫 请求起飞` in the user-facing reply only when current evidence confirms
every applicable prerequisite in the requested preflight scope is ready. Name
the Tasks and checks actually verified, distinguish preview and collection from
execution and acceptance, and give the concrete next action. If any applicable
check is unverified, failed, or blocked, or coverage is incomplete, omit both
`🛫` and `请求起飞`. Report the verified scope, the specific gaps and the next
action, even when the selected Task is ready within a partially checked route.

Carry forward existing execution authorization for the covered action without
asking again. Name any outstanding authorization and the action it gates, and
keep it open when it is an applicable prerequisite for that action.
Design confirmation, human acceptance and execution permission retain their
own gates. Return to the authorized calling flow when preparation is sufficient.

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

Base blockers on observed evidence. Check any claimed mismatch in a structured
value with a deterministic read-only check when possible. For hashes, compare
the observed and expected values and validate the format mechanically before
reporting a length or content mismatch. Carry forward a successful recorded
collection when it covers the exact selectors and there is no observed
incompatibility with the planned runner. If compatibility is an explicit
requirement and the record leaves it unresolved, state what remains unverified.

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
