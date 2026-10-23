---
name: lb-push
version: 0.5.0-dev
description: "Advance or resume a confirmed Logbook through its authorized endpoint. Preserve explicit Captain takeover across subsequent tasks; otherwise dispatch Sailors or select automatic problem-specific takeover. Stop at human gates or concrete blockers. push means project advancement, not Git push; use lb-status for queries."
---

Read the [document state and CLI failure recovery contract](../../docs/installable/document-state.md).
If lb is unavailable or crashes, notify the user and take over safe authorized work;
report pending writes and verification gaps instead of silently stopping or bypassing CAS.


Captain coordinates the Logbook route and selects its executor under the [takeover and handoff contract](../../docs/installable/coordination.md#scoped-takeover-and-execution-handoff). Align the actual executor’s current result (task/package, result, conditions, outcome and gaps) before recording completion. Status/update-only requests start no business work or execution-mode switch.


# Advance Project Tasks

The mode is advance, resume, or cleanup (release approved resources). Advancement not limited to a single item runs serially along the confirmed list; an explicit single item or batch respects its endpoint. Mode or skill switching never expands authorization.

## Inputs and Preconditions

On every invocation with the lb CLI, read `log context` and its `execution` state;
follow the [JSON execution contract](../../docs/installable/lb-cli.md#execution-state-in-project-json).
A pending/released dispatch-only handback does not permit unrelated agents.
Read the target logbook from disk and verify goals, non-goals, working directories, the complete ordered list, authorization, and existing report-backs; never substitute session memory or stale line numbers. Must read the [Configuration Contract](../../docs/installable/configuration.md) (including collaboration parameters), [Execution and Recovery](references/execution.md), and the [Coordination Contract](../../docs/installable/coordination.md). Consult the human when a parameter required by this step is missing and read-only verification cannot fill the gap.

When creating or replacing a session, parse the full launcher; even when reusing, verify the actual model, deployment, and input boundaries. Runtime operations determine runtime.adapter and its actual capabilities; before controlling Herdr, read the [Herdr Adapter](references/herdr.md) and the environment's tool skill. When a capability is missing, stop the dependent step; do not bypass wrapper, monitoring, or isolation requirements.

Before writing, read the [Logbook Format](../../docs/installable/logbook-format.md) and the [Document Adapter Process](../lb-update/references/document-adapters.md). Maintain only the approved list, statuses, and short facts; preserve human goals, large prose bodies, and existing heading wording and numbering.

Apply explicit human decisions to unfinished agent-task text through `task rewrite`, preserving scope and evidence correspondence. Human wording remains protected; actual human work/review starting may be recorded as `[ ] → [/]`, never completed, cancelled or reverted by the agent. Keep process details in Thinking and original-source pointers in existing host records.

## Design and dialogue gates

Before advance or resume, read the current repository spec and its applicable Admiral confirmation under the [design contract](../../docs/installable/coordination.md#design-state-and-execution-readiness). Ordinary execution requires a settled core design, confirmed route and execution authorization; a complete list or green preflight cannot supply missing design decisions. Reuse valid confirmations without asking again. Work packages identify relevant spec content, constraints and criteria. Route material design choices back to Captain; routine implementation remains Sailor's responsibility.

The bounded POC exception requires an explicit todo, a reorganized route discussed and confirmed with Admiral, a clear POC question/scope/criteria and execution authorization. Stop at its endpoint and recover findings into design discussion, even under a previously broad advancement request; do not fall through to ordinary implementation while the core design remains unsettled. Preserve existing human and 🔮 gates. Cleanup and status-only handling do not demand new design approval.

For direct Admiral–Sailor discussion, Captain must permit and open a usable dialogue entry, then recover submitted content and decisions before affected execution resumes. Follow the [dialogue procedure](references/execution.md#direct-admiralsailor-dialogue); opening the window is not completion of the handoff or authorization for more work.

## Execution-mode selection

At entry, task completion and interruption recovery, read the human instructions
and checkpoint before choosing an executor under the [mode contract](../../docs/installable/coordination.md#scoped-takeover-and-execution-handoff):

- **Explicit takeover:** Captain personally executes the whole authorized
  advancement unless the human narrowed it. Task completion, later lb-push items,
  skill changes, stale checkpoints and earlier parallel approvals do not release
  it. Continue ordinary tasks personally; leave required independent review
  pending and report the conflict. Resume delegation only on explicit human
  permission or a previously authorized release condition, through
  [lb-handback](../lb-handback/SKILL.md); a general continue is not a release.
- **No explicit takeover:** normally dispatch Sailor. A direction-setting problem,
  coupled investigation or repeated ineffective repair can trigger bounded
  [lb-takeover](../lb-takeover/SKILL.md) within existing authority, followed by
  [lb-handback](../lb-handback/SKILL.md) at its scoped exit. A routine error,
  missing return or timeout alone does not justify takeover.

Respect host execution restrictions. Mode changes need no repeated approval and
preserve counters, human gates and the authorized endpoint. With no remaining
executable work, align results without an empty dispatch. Status/update and
cleanup entries start no execution-mode change.

## Advancement Loop

Before any executor launch, resume or prompt, recheck the takeover boundary above;
it takes precedence over the parallel, review, context-rotation and dispatch
procedures below.

At initial route reading, after each applicable acceptance return, and when waiting/blocked, inspect parallel opportunities within the current authorized route. Compare actual input/output and human dependencies, owners, mutable files and shared resources. Different repositories/worktrees/titles alone do not prove independence. Describe a concrete batch with owners/results, input snapshots, isolation, convergence and authorization, or state the actual dependency. Proceed with approved batches without asking again; propose unapproved batches once while continuing unaffected approved work. Discovery alone does not authorize launch, reordering, scope expansion or crossing a human gate.


When dispatching, reusing, or waiting for report-backs, watch the execution session's context usage. Above 80%, run GC automatically without re-confirmation: save the work package, worktree, candidates, evidence, open responsibilities, and unsent inputs; end the old session at a safe boundary; start a new session with a compliant wrapper, continue in the original worktree, and rebuild monitoring. Do not inherit the old context wholesale, and do not wait for `/compact` instead of GC. When the old session cannot provide a handoff, recover from the verified logbook and disk state, first reconciling unfinished operations to avoid duplicate side effects. Keep uncommitted changes and services still in use; do not delete the worktree; do not reset acceptance or review counts. When usage is unknown, do not infer it from credit/quota. Count completed work packages since launch or last verified rotation; at limits.context_unknown_packages (default 3), hand off and rotate at the next safe package boundary. When prior count is unknown, checkpoint and rotate before taking another package once current operations are reconciled. Record the rotation basis in Thinking. Never interrupt an external operation merely to satisfy the counter; reclaim only execution sessions this project is authorized to manage. When entering from lb-status, only perform the GC — resume the original task only if it still carries execution authorization; do not dispatch a new task.

When `settings.runtime.quota` is configured, check the candidate provider's usage before dispatch, reuse, and GC, and apply the [quota watermarks](../../docs/installable/configuration.md#quota-watermarks); account quota still never stands in for context usage.

In normal mode, browser work goes to the Sailor using the host-declared browser tools with a task-scoped session; when a pinned profile is needed, read `browser.profile` from `lbkit.yaml`, and consult the human when it is missing and cannot be inferred from the task. Verify browser ownership at dispatch and acceptance; a session name alone is not proof. Never connect to or take over the human's main browser, never delete locks or close user windows; when the profile is occupied, report the conflict instead of force-reusing. Logins are completed by the human in an automation-dedicated browser.

1. Reconcile lifecycle under [lifecycle operations](../../docs/installable/lifecycle-operations.md): paused/terminated/completed do not authorize dispatch; record active only on actual authorized start through `log state-set`, and route explicit pause/termination to lb-update. Following the [CLI Reading Process](../lb-update/references/document-adapters.md#cli-invocation-in-this-repository), run `log context --json` on the current logbook and verify the first item against the original text and authorization; never trust `next_task` alone. advance selects the first unfinished (`[ ]` or `[/]`) item in document order, skipping `[-]`, which is neither pending work nor a blocker; resume verifies the original package, current list, and authorization. Resume an existing Sailor of the same package instead of re-dispatching; a blocked first item is not skipped. The exception is a human item with a confirmed `状态：🔀 可越过：` sub-line: it stays an open human gate (checkbox and first line untouched, still reported as pending), and advancement continues with the following agent items, stopping before any item that needs that human result, before the next human item without the marker, and at stage close, which waits for the human item. `next_task` still returns the human item; the sub-line, not the parser, decides. When the plan is human-confirmed and inputs are ready, dispatch proactively — do not stall at "ready to start". New or restructured plans must satisfy the lb-plan exit criteria: human goals authored or transcribed verbatim, and working directories, Stages, and item-by-item todos confirmed, plus the design gate above.
2. Verify the work package's result, scope, inputs, owner, dependencies, evidence gates, and any required finite review rounds. Missing facts within authorization are investigated by the owning agent; consult the human for out-of-scope information. When an evidence gate requires E2E, a real environment, quality reports, or key-step screenshots, never downgrade it to a static check; Sailor performs the actual agreed checks and returns applicable outcomes.
3. Select the actual recipient under the [recipient selection rules](references/execution.md#runtime-adapter-contract) before choosing any launcher: resume an existing suitable executor when not ready, or send to it when ready. Only permitted creation/replacement selects a launcher; filter its declared options by input sensitivity and task needs. Sensitive inputs, or inputs of unknown classification, go only to confirmed internal deployments; the same applies to reuse, sub-agents, and evaluations. Prefer the Captain’s machine for new work; remote exceptions retain directory/model permissions. For new dispatches, identify the task, create its dispatch record, and bind creation-returned machine/workspace/tab/pane/agent/session IDs with `agent bind` under the [domain command contract](../../docs/installable/domain-commands.md). Record sent/acknowledged only from actual transport and receipt evidence; keep attempts separate from task acceptance. Before control, verify the live recipient, input and ownership; saved resolve/check is offline evidence. Use full IDs or a verified unique agent name, never list indexes. Dispatch the full work package in the responsible repository through the selected runtime adapter; business execution uses an isolated worktree. An existing independent reviewer already satisfies implementer isolation; review or parallelism requirements alone do not justify duplicating it. In normal mode the coordinator does not implement or set up environments on Sailor’s behalf; scoped direct work must first enter lb-takeover.
4. Close dispatch in this order, for both new and reused executors:
   - Read back the actual package receipt and execution state; trust gates and
     empty tabs are not receipts.
   - Establish and verify the adapter's independent visible read-only monitor
     (for Herdr, a separate tab/pane with a status-wait bound to this dispatch;
     `agent get/read` is not a monitor). Repair missing monitoring on the same
     executor without resending.
   - **Then** write the chosen executor, released scope, observed receipt and
     monitor evidence, pending review and Captain duties into the existing
     Thinking/host record and read it back. Replace plans such as “next: verify
     receipt” with results or the specific remaining gap; runtime state or a
     final reply is no substitute. This applies at a receipt-only endpoint too.
   If readiness or ownership is pending, record the partial result and owner and
   do not report transfer complete. For managed CLI records, mark dispatch
   acknowledged, start its attempt and the identified task (`task start`, or
   legacy `task update --status /`), then `log sync` and `log check` with current
   version_token, previews and readback. A read-only Logbook does not forbid the
   execution JSON. Workspace/focus/naming rules follow the runtime adapter.
5. After waiting, read the latest status and output. `idle`, `done`, or `blocked` triggers report-back or blocker verification — never a direct checkbox tick; while still `working`, judge progress from new facts. A single wait is bounded by limits.wait_seconds; usually 10 consecutive minutes without effective progress triggers a stalled-method diagnosis — judge per the task's nature, and never drag on with repeated waits or session restarts. At the limit, verify the scene, stop repeating the failed method, and pursue evidence-based recovery within the original scope; escalate only a real remaining decision or unavailable prerequisite; never kill the process just because a wait expired.
6. Execution deviating from the confirmed plan can be corrected within the original scope; when the confirmed plan itself is wrong in direction, on major decisions, on out-of-authorization key information, on login approvals, or on scope changes, stop and consult the human. Handle routine issues within the original task yourself; do not bounce work the owning agent could complete back to the user. When candidates, samples, tools, or environments are missing, do not substitute a report full of "unknowns" for the original deliverable; keep the received item at `[/]` and record the blocker per the facts.
7. The current actual executor’s result/conditions/outcome/gaps must be aligned and written back via [lb-update](../lb-update/SKILL.md), preserving the review rounds already used. After acceptance passes, re-read the original text and `log context`, then continue to the next item within the existing advancement authorization and retained takeover restriction; stop at an explicit single-item/batch endpoint, a human gate, a severe blocker, or full completion. New items, reorderings, and scope expansions still require human decision — continuous advancement is not a license to overstep.

Before the first external write, verify the authenticated identity belongs to the human owner, and write any body in their judgment and voice — never cast a coordinator or Sailor as the externally accountable party. Authenticated profile or a verified account mapping can establish ownership; key names or local authorship cannot. Pause the dependent write when identity or voice is unclear; a tooling capability gap does not authorize switching to a semantically different channel. When the write publishes a reviewed result, verify feedback clearance on each surface separately — thread comments, review threads and inline comments each state their own resolution; an empty surface clears only itself and never substitutes for the others.

cleanup touches only approved resources; it does not pick a business first item or dispatch follow-up tasks. Deleting a completed worktree follows the consuming repository's applicable cleanup authorization; reuse, retention, and cleanup of sessions and monitoring are judged by the model against the scene, without affecting other projects.

## Reporting and Handoff

For configuration-driven operations, align evidence of the effective change and outcome with the task criteria and actual tool capabilities under the [return contract](../../docs/installable/coordination.md). For pipelines, check the run/effective configuration, required-task inclusion and terminal results; startup or overall success with a missing required task cannot satisfy the full package. Request a missing pipeline identity when needed to establish correspondence; never infer it from a package/session name. For tools without run IDs or graphs, use applicable target/digest, exit status and owner readback evidence instead; do not invent an unsupported evidence gate.

When an authorized execution task needs correction, name the observed discrepancy and the specific missing evidence in the actual message to its existing owner, then verify receipt. Do not merely ask for generic “evidence”, repeat routine permission questions, create duplicate executors or expand repair scope. A completed diagnosis does not authorize repair: keep the diagnosed operation's failure distinct from the investigation's completion and follow the task's own endpoint.

Choose handoff entries by the human's actual use: current result, review/action entry and essential limitations. Do not list every report, work package or raw record in the main logbook. Copy the exact destination verified under the delivery contract into the final handoff; record missing delivery truthfully without inventing a new gate. Keep key identities and recovery instructions in Thinking and authoritative pointers in existing host records. Before cleanup, check those references survive or record the explicit retention/discard decision.

Report receipt facts, the executor's location (Herdr name, workspace, tab/pane), monitoring, results or blockers, and who does what next and when it resumes; do not report focus. Separate operational facts from acceptance conclusions; no report-back never implies completion.

When a human must take over, re-read the logbook before replying to get accurate file and line numbers, and state the verified facts, attempted approaches, possible decisions, and unblock conditions. For logins or approvals, give the specific system, object, page or session location, and the completion marker; for major decisions, explain the tradeoffs. When facts are insufficient, fill them in within authorization first — do not make the user explore blindly. For any out-of-plan matter that needs the human owner and cannot advance, write `🚨` plus the blocker cause, the concrete action, and the unblock condition at the very front of the item body, keeping the original status (received items stay `[/]` — no ticking, no adding or moving tasks; human-owned items may be marked in-progress only when human work has actually begun); conversational reporting does not substitute for a logbook write-back. Human todos already marked `👱` in the plan just stop at the gate — do not add `🚨`; blockers an executor is handling itself await its report-back and escalate to `🚨` only when verified recovery still needs a human decision, credential or scope expansion.

When no human takeover is needed, state the owning agent's next action and report-back conditions, and continue authorized work without turning a progress report into task-level confirmation. At the authorization endpoint, state clearly what was completed and what the next item is; do not start it on your own.

Before human handoff, apply the [delivery contract](../../docs/installable/coordination.md#human-deliveryreadiness--us4). Have Sailor complete authorized delivery work and return the inventory/binding outcome; align it with the current PR or branch/candidate entry. Continue missing delivery steps within existing authorization, or report the concrete conflict before presenting the human gate as ready.

## User-facing line guidance

Apply the [locator guidance](../../docs/installable/coordination.md#human-facing-logbook-locators) to progress reports, blockers, decisions and handoffs: give the current task or human gate as `L50` plus its name, and the next item's line when reporting an endpoint. After writeback, reread positions before replying. Keep the verified result/review/login entry alongside the Logbook locator so the human can both locate the route item and perform the action; existing authorization still permits continuation without a new confirmation.

## Requested run metrics

Use `lb log events record` during work to record start/end/resume, waits/interruptions, human turns and first acceptance/corrections in bound Thinking under the [event contract](../../docs/installable/coordination.md#run-event-and-close-out-metrics). Collect actual skill usage and lessons on returns; replace stale current status instead of appending a transcript. Resume keeps the same run and counters. Captain records coordination facts; Sailor returns actual acceptance facts and later defect corrections. Do not archive raw trials or create a metrics sidecar.

At Stage/logbook 🎉, report exact scope, wall elapsed with waiting/interruption union, human interaction count/categories and first-pass numerator/denominator/rate. Call lb-update’s closeout flow with `lb log report --view metrics`/`lb log report --view closeout` for deterministic arithmetic; no event history or zero denominator gives explicit unknown/no-calculable-data, never invented success. A corrected delivery defect removes an erroneous first-pass pass even if rework later succeeds. Metrics do not complete human gates or create a checker role.
