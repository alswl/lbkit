---
name: lb-handback
version: 0.5.0-dev
description: "Return execution to Sailor when the human permits delegation, a human-authorized release condition is met, or an automatic problem-specific takeover ends. Completing a task does not release explicit Captain takeover. Verify receipt, readiness and ownership reconciliation; Captain retains coordination. Use lb-update for Sailor returns, not this skill."
---

Read the [document state and CLI failure recovery contract](../../docs/installable/document-state.md).
If lb is unavailable or crashes, notify the user and take over safe authorized work;
report pending writes and verification gaps instead of silently stopping or bypassing CAS.


# Hand execution back to Sailor

Transfer only authorized execution to Sailor. The current session remains Captain,
retaining coordination, route decisions, monitoring, return alignment and human
communication. Closing one task's status does not release takeover for later tasks.

Read the [takeover contract](../../docs/installable/coordination.md#scoped-takeover-and-execution-handoff),
current Logbook, actual takeover checkpoint/result, spec and host authorization.
Resolve the coordination root separately from the business worktree and use the correct cwd for each operation. Use [execution rules](../lb-push/references/execution.md) for runtime operations and
[document adapters](../lb-update/references/document-adapters.md) for guarded writes.

Before selecting an executor, recover the release permission: an explicit human
instruction to resume dispatch or a met, previously authorized release condition.
Task completion, old checkpoints, prior parallel approval and later lb-push do not
release explicit takeover. Preparation-only permits read-only runtime inspection.
Preserve running work outside the authorized handoff.

1. Reconcile what Captain actually resolved against the takeover exit condition
   and Admiral's current instructions. Separate verified facts, hypotheses,
   failed operations, uncommitted edits and remaining work. Do not turn handoff
   into a completion claim or silently abandon the unresolved takeover objective.
   An explicit early handoff records the unresolved problem and human direction.
2. Update existing spec/Thinking/host records within authorization. Identify the
   exact repository/worktree/ref/candidate (including dirty changes), inputs,
   decisions, previous failed methods, checks/outcomes/limitations and open duties.
   Preserve task identities, review usage, first outcomes and human/POC gates.
   Adjust route/scope only under the applicable lb-plan/Admiral authority.
3. Select the exit before creating or sending a package:
   - **No executable work remains:** align the direct result through lb-update,
     replace the takeover status with the actual result/coordination status
     without 👨‍✈️, and stop at the current endpoint (or return to an already
     authorized next route item personally under retained explicit takeover).
     Closing a completed task does not clear the advancement-wide restriction
     or authorize a tester for the next task. Do not send a completed-result announcement,
     empty package or review request to Sailor; do not pause or rebind runtime.
     An open human review gate alone is not remaining Sailor work.
   - **Work remains but execution or delegation is not authorized:** save the remaining package
     in existing Thinking as 'handoff prepared, not sent', with next action and
     needed authorization. If ordinary work remains under explicit takeover,
     return to Captain's personal execution; if the next item requires independent
     review, retain it pending and report the conflict without dispatch or
     substituting self-tests. Runtime inspection remains read-only.
   - **Work remains and execution plus delegation are authorized:** continue with steps 4–6.
4. With the lb CLI, read [execution context](../../docs/installable/lb-cli.md#execution-state-in-project-json)
   and record the existing release instruction, or the authorized condition with
   its check result, naming the receiving dispatch/recipient and scope; recording
   is not a new approval request, and a matching release is reused on recovery.
   Prepare the remaining package with result, permissions, constraints, input
   snapshot, acceptance criteria and report-back entry. Required independent checks
   stay with Sailor on the actual candidate; Captain self-tests do not count. Follow
   the [token workflow](../../docs/installable/lb-cli.md#target-file-tokens-and-a-minimal-recording-workflow)
   and stop to review changes on a CAS conflict.
5. Resolve the requested/original Sailor with the
   [recipient selection rules](../lb-push/references/execution.md#runtime-adapter-contract):
   reuse it when present and suitable, resume it when paused or not ready, and
   create/replace only with permission and a concrete reason. Under
   [lifecycle operations](../../docs/installable/lifecycle-operations.md), keep
   dispatch/run/counter identities, reconcile saved bindings with the live
   recipient, and use full Herdr IDs or a verified unique name, never list indexes.
   Send the complete package and verify receipt plus execution/monitoring
   readiness; a chat summary or created tab is insufficient. `lb agent send` needs
   a stable operation ID and current Thinking and execution tokens; an unknown
   outcome requires reconciliation, never a new ID or resend. On failure keep the
   handoff open, avoid concurrent writes, repair only the missing step and reuse a
   verified receipt. Keep `👨‍✈️` with the pending handoff fact while Captain still
   owns execution, using protected note replacement.
6. Record receipt, execution readiness, monitor readiness and ownership as separate
   sourced observations through `log execution record`, including unknown values.
   A submitted message is not readiness or review. Once evidence supports
   completion, sync the page projection, replace the task note through protected
   writes and read back; repair JSON/Markdown disagreement without another handoff.
   Non-CLI hosts reconcile equivalent records. Return to [lb-push](../lb-push/SKILL.md)
   within the original endpoint and release scope. Status-only invocations do not
   send packages or start continuation.

## User-facing line guidance

Follow the [shared presentation and release rules](../../docs/installable/coordination.md#scoped-takeover-and-execution-handoff)
for the `👨‍✈️` prefix in progress and final replies, including after interruption.

In preparation, pending-transfer and completed-handback replies, apply the [locator guidance](../../docs/installable/coordination.md#human-facing-logbook-locators): identify the affected Logbook task at its current `L50` position, who owns execution and the next action. Give any remaining human gate its own verified line, and retain the usable result/runtime entry. Reread after status reconciliation; a line reference is not proof of receipt or readiness.

This hands business execution back to Sailor. Cross-machine Captain migration,
final human delivery, resource cleanup and Git publishing retain their separate
contracts and permissions. Execution JSON does not authorize publication or cleanup.
