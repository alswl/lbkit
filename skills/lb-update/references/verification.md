# Return Alignment and Wrap-up

Read the [format](../../../docs/installable/logbook-format.md) and [coordination](../../../docs/installable/coordination.md) contracts before protected writes.

1. Re-read the current Logbook/Stage/task and authorization, including explicit human rulings. Keep concurrent human edits and original ownership.
2. Align the Sailor return: current package/task, result/revision, inputs/conditions, acceptance outcome, actual delivery entry, remaining responsibilities and limitations. Business acceptance, tests and original observations are Sailor tasks. Captain verifies correspondence and readiness/control facts rather than rerunning business work. For business review sheets, do not compare original/repaired candidate rows, recount headers/table sizes or recompute layout budgets to produce a fresh pass. These are Sailor checks even when called return alignment; use the identified Sailor outcome or retain a gap.
3. Changed results, inputs or conditions invalidate affected conclusions until Sailor rechecks applicability. A new token, runtime idle/done/exit or bare completion claim proves no acceptance. Failed/incomplete/unknown/missing/conflicting returns leave the item incomplete. An update-only request launches no investigation or rework.
4. Required independent checks use another Sailor on the same candidate and retain finite rounds. Do not create an acceptance role or default extra checker. Existing execution authorization covers routine rework; scope changes and human gates need the applicable Admiral decision.
5. Protect human items: only actual human work starting may be recorded as `[ ] → [/]`; do not complete/cancel/revert them. An explicit skip ruling may disposition an existing skipped agent task without claiming successful delivery.
6. When the confirmed delivery requires a PR, before its review/merge gate, align the actual accessible PR and current head with the Sailor result. Local-only results or an old PR are not ready. Sailor owns authorized commit/push/PR creation; human merge remains separate. Verify the full file list follows host layout/content/source-binding rules, not temporary-material names.
For an explicit branch-only ruling, align branch/ref/candidate and its usable review entry instead. Distinguish uncommitted working-tree changes from branch HEAD; infer no commit/push/merge permission and invent no PR gate.

7. Preserve useful decisions/recovery in existing bound Thinking and host-owned business records. No mandatory source index, raw-output archive, file-per-return or copied business content is required. Preserve human comments and avoid cleanup that destroys their recovery pointers.
8. Write only minimal authorized progress through [the document workflow](document-adapters.md), inspecting the diff and using the returned token for sync/check. Close distinguishes achieved goals, accepted deviations, cancellations, open responsibilities and actual human rulings; it creates no extra human gate.

Report actual writes, applicable return identities, outstanding gaps and the next owner. Cleanup is separately authorized.

## Requested run metrics

Record run start/end/resume, human waiting/interruption, distinct human turns and applicable first acceptance/corrections in the existing bound Thinking using the [event contract](../../../docs/installable/coordination.md#run-event-and-close-out-metrics). Resume keeps the same run and counters. Captain records coordination facts; Sailor returns actual acceptance facts and later defect corrections. Do not archive raw trials or create a metrics sidecar.

At Stage/logbook 🎉, report exact scope, wall elapsed with waiting/interruption union, human interaction count/categories and first-pass numerator/denominator/rate. Use the read-only `skills/lb-push/scripts/run-metrics.py` helper for deterministic arithmetic; no event history or zero denominator gives explicit unknown/no-calculable-data, never invented success. A corrected delivery defect removes an erroneous first-pass pass even if rework later succeeds. Metrics do not complete human gates or create a checker role.
