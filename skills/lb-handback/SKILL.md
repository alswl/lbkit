---
name: lb-handback
version: 0.4.1-dev
description: "Return a scoped Captain takeover to normal Sailor execution. The current session stays Captain and retains coordination. Use when asked to hand back execution or resume delegation, and automatically when lb-takeover reaches its exit condition. Recover current design/candidate/checks, prepare remaining work and verify the receiving Sailor's actual receipt before resuming lb-push. Not a generic human delivery or cross-machine Captain migration skill."
---

# Hand execution back to Sailor

The current session remains Captain before, during and after handback. Transfer
only the identified business execution scope to Sailor; retain project coordination,
route decisions, monitoring, report-back acceptance and Admiral communication.
Removing the takeover marker ends direct execution, never the Captain role.
Do not appoint Sailor as Captain or close/replace the Captain session.

Read the [takeover contract](../../docs/installable/coordination.md#scoped-takeover-and-execution-handoff),
current Logbook, actual takeover checkpoint/result, spec and host authorization.
Resolve the coordination root separately from the business worktree and use the correct cwd for each operation. Use [execution rules](../lb-push/references/execution.md) for runtime operations and
[document adapters](../lb-update/references/document-adapters.md) for guarded writes.

First determine whether this is preparation-only, result close-out, or an authorized execution transfer. Preparation-only allows reading available runtime facts, but never pausing Sailors, changing monitor bindings or sending work. With no executable work remaining, reconcile recorded results without manufacturing a runtime pause/transfer. Preserve existing running work outside the authorized handoff.

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
     without 🧑‍✈️, and stop at the current endpoint (or return to an already
     authorized next route item). Do not send a completed-result announcement,
     empty package or review request to Sailor; do not pause or rebind runtime.
     An open human review gate alone is not remaining Sailor work.
   - **Work remains but execution is not authorized:** save the remaining package
     in existing Thinking as 'handoff prepared, not sent', with next action and
     needed authorization, then stop. Runtime inspection remains read-only.
   - **Work remains and execution is authorized:** continue with steps 4–6.
4. Prepare the executable remaining package with result, permissions, constraints,
   input snapshot, acceptance criteria and report-back entry. Required independent
   checks stay assigned to Sailor on the actual candidate; Captain self-tests are
   attributed to Captain and do not count as independent review.
5. Prefer the original Sailor if its model/context/data boundary remains suitable.
   Verify the actual recipient and current worktree; reconcile its stale package
   and any pending commands. Send the complete current package via the host adapter
   and verify actual receipt plus required execution/monitoring readiness. A final
   chat summary or a created tab is insufficient. If receipt/readiness fails,
   retain an open handoff responsibility and the current candidate, avoid concurrent
   writes, and repair only the missing step within authorization. Reuse verified
   receipt on retry; do not create a duplicate executor or resend side effects.
   While transfer is pending, retain `🧑‍✈️` in the current task status with
   the pending handoff fact. Receipt without required readiness still leaves it
   pending. Preserve unrelated status text and use protected note replacement.
6. After confirmed receipt and readiness, finish the transfer by recording the receiving executor, scope and next action
   in the existing checkpoint. Replace the matching current task status with Sailor execution status without 🧑‍✈️ through token-guarded `task note --replace-line`; do not change task first line. Status replacement is supported by the current CLI: a refusal requires correcting the token/task/line/kind or reporting the concrete gap, not falling back to a direct Logbook edit. Return to [lb-push](../lb-push/SKILL.md), continuing
   within its original endpoint without asking again. A receipt-only execution endpoint still includes this ownership/status writeback; it excludes subsequent business execution, not handoff reconciliation. Do not report handoff complete while the current checkpoint or task status still says Captain is executing. Status-only invocations neither send packages nor start this continuation.

## User-facing line guidance

In preparation, pending-transfer and completed-handback replies, apply the [locator guidance](../../docs/installable/coordination.md#human-facing-logbook-locators): identify the affected Logbook task at its current `L50` position, who owns execution and the next action. Give any remaining human gate its own verified line, and retain the usable result/runtime entry. Reread after status reconciliation; a line reference is not proof of receipt or readiness.

This hands business execution back to Sailor. Cross-machine Captain migration,
final human delivery, resource cleanup and Git publishing retain their separate
contracts and permissions. No new state field, archive or configuration is needed.
