# Acceptance and wrap-up workflow

Must be read before handling new results, confirmed decisions, or final wrap-up. Evidence terminology is in the [evidence model](../../../docs/evidence.md); logbook display is in the [format](../../../docs/logbook-format.md).

## Verify first, then write

1. Re-locate the current checklist item and its original acceptance gate, and check the user's concurrent edits; when evidence references an old item or old version, confirm the correspondence first.
2. Fix identity by deliverable type, then verify candidate, environment, time, and original records. Code uses commits; reports may use a fixed version or summary; environments use change records and observation timestamps — not every deliverable type requires a PR.
3. Verify the required independent checks: the checker differs from the implementer, targets the same candidate, and returns original evidence rather than restating a summary. When a required check has not returned, the round limit is reached, or evidence identities disagree, state the gap explicitly; this workflow does not dispatch checkers itself.
4. When the project has a PR, verify its current state; a merge gate requires merged evidence with a matching identity. squash/rebase can change SHAs — a reliable correspondence is required. If it cannot be verified, keep it unknown; never declare a merge from stale records.
5. Judge each gate as pass, fail, insufficient evidence, or pending human decision. After a candidate, environment, or acceptance criteria change, old evidence does not by default support new completion conclusions for the affected items; carry it forward only when a verifiable candidate correspondence and original records prove it still covers the current gate. Similar task names, a refreshed token, or a user saying "keep updating" are not such proof. Do not stitch versions together, and do not erase unrelated historical facts.
6. Check a box only when the result meets the gate. Failures and evidence gaps stay on the original item, recording the owner, the missing facts, and the clearance conditions; do not expand remediation scope or quietly lower the bar.
7. Write back and check per the [document adapter workflow](document-adapters.md). Report updates and unfinished parts, and stop at this round's authorization boundary.

An existing, definite, and applicable acceptance conclusion may be cited directly, but its subject and basis must be traceable. A user asking to "just tick it" does not waive verification. Cross-repository investigation and test reruns are the owning executor's job; an update request itself authorizes no new dispatch.

## Project wrap-up

Summarize whether goals were met, the identity of final deliverables, applicable merge or release results, deviations, and remaining responsibilities. Without a final human decision, remain pending acceptance; with an explicit decision applicable to the current deliverable, record it directly without asking again.

When the human accepts a deviation, record the new decision's basis and impact; never rewrite history as if the original standard passed. Unconfirmed follow-ups are recorded as pending-decision information; do not auto-create manifests or external work items. Cancellation or termination may end coordination, but must not be recorded as a successful delivery.

Wrap-up updates do not close execution sessions or other services. Necessary cleanup is left to lb-push's authorized cleanup branch, handing over unfinished responsibilities and resource scope.
