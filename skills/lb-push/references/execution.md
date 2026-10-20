# Execution, Review, and Recovery

Read before dispatching, resuming, or authorized cleanup. This file defines the operating process; tool commands come from the selected adapter. The boundaries in the consuming repository's root `AGENTS.md` and the [Configuration Contract](../../../docs/installable/configuration.md) always apply.

## Runtime Adapter Contract

Before execution, verify the selected adapter provides: explicit executor targeting, preserved human focus, an isolated execution space, task submission with receipt confirmation, independent visible read-only status waiting, and report-backs tied to this dispatch. Report the specific gap if any is missing; never fabricate capabilities or pass polling off as monitoring.

The [Herdr Adapter](herdr.md) is currently provided and must be read and followed only when runtime.adapter=herdr. Other environments must supply reliable adapter documentation and capability evidence; no automatic switching. The visible monitoring requirement declared by the host repository cannot be configured away.

Existing sessions that meet requirements may be reused; do not restart just to re-parameterize. Only new or replaced processes require parsing a launcher; choose from the declared candidates per need, replacing command and args atomically without mixing in old parameters. Reuse still requires verifying the actual model and data boundary before sending material; a failed launch does not authorize calling some other model directly.

## Dispatch Loop

1. Locate the work package, executor, authorization, and isolated space; confirm inputs and dependencies are ready, and that prerequisites for the first external write, including authenticated identity when applicable, are satisfied before that write. Check that the executor's sandbox can reach what the package needs: a worktree's Git metadata lives in the main repository outside the worktree, so a workspace-write sandbox fails `git commit` on `index.lock`; Docker sockets and network access may be blocked the same way. These limits are fixed at launch, so choose a launch option that covers them before dispatch instead of discovering the failure mid-package.
2. Hand the full task to the owning executor, obtain proof of receipt, and observe real status. Report the launch gate, task receipt, and business execution separately.
3. After receipt, establish independent visible monitoring tied to this dispatch and verify monitoring readiness. A successful run with failed monitoring is a partial completion; fix the monitoring, and do not resubmit the business task.
4. Each status wait is at most limits.wait_seconds; this is not a task execution deadline, and one expired wait never justifies killing the executor. Immediately after each wait, read the latest status and output: if `idle`, `done`, or `blocked`, stop waiting and handle the report-back or blocker; if still `working`, report the new command, artifact, or evidence, or the concrete basis for calling it stalled. Never repeat waits without refreshing status and output, and never treat one `working` snapshot as continuous operation. Keep progress human-visible.
5. Hand received report-backs to lb-update's applicable-return process. Tie gaps to the original package; after acceptance, re-read the logbook and move to the next item within the existing advancement authorization; stop at an explicit single-item or batch endpoint, a human gate, or a severe blocker — acceptance itself is not an authorization expansion.

## Direct Admiral–Sailor Dialogue

Apply the [dialogue contract](../../../docs/installable/coordination.md#captain-mediated-admiralsailor-dialogue). Captain permits the scoped conversation and opens an actual host-supported interaction window for the owning Sailor/package; verify the recipient, usable entry and recoverable submitted conversation. Reuse the owning session where supported, preserve focus/unsent input and avoid duplicate dispatch. With Herdr, follow the [adapter](herdr.md#direct-dialogue-window); other adapters must provide verified capabilities rather than invented commands.

Keep automated task submissions out of the human's active dialogue entry. After discussion, retrieve attributable Admiral instructions and Sailor responses, recover conclusions and pending decisions in Thinking, and update affected specs/Logbook/packages within their write rules. Preserve explicit newer Admiral rulings without asking for them again; a reported conversation without attributable content cannot establish approval. Verify Sailor received the reconciled package before resuming affected work. Do not mark acceptance from dialogue, cross a gate, or clean up the entry before recovery. If content is unavailable, state the missing decision and leave dependent work pending.

## Independent Checks and Finite Rework

Business execution and acceptance normally belong to Sailors; authorized direct Captain execution follows the [scoped takeover contract](../../../docs/installable/coordination.md#scoped-takeover-and-execution-handoff). Captain aligns returns and control facts. Another Sailor performs an independent check only when the package requires it; no separate acceptance role or default checker is introduced.


When independent checks are needed, the implementer first fixes a candidate, then the same identity goes to different checkers. Checkers do not modify deliverables; they return pass, fail, or evidence-linked gaps. Each time a candidate goes to an independent check counts as one round; the first round counts against limits.review_rounds; multiple checkers reviewing the same candidate are one round.

Return only relevant gaps to the implementer, and re-verify affected results with the new candidate; preserve rounds already used. Stop and hand to the human at the cap, when required authorization is missing, or on major tradeoffs — never dodge the cap by switching skills, restarting sessions, or splitting new packages. `review_rounds` bounds the rounds a candidate goes to independent check; human review rework rounds on the same PR (review → fix → CI → respond) do not consume that quota, but when the same kind of review repeats without substantive convergence, report to the human owner per the stalled rules instead of responding indefinitely.

## Blockers and Recovery

Before retrying, verify existing candidates, external state, and unfinished operations via the control plane or the owning agent to avoid duplicate side effects. Set applicable tool timeouts for CLI, MCP, or network calls; limits.wait_seconds does not directly cap total business command time.

Judge timeouts per the task's nature, usually with 10 consecutive minutes without effective progress as the limit; effective progress means new facts, command results, artifacts, or evidence — repeated status text does not reset the clock. For builds or tests of known duration, set deadlines per the task's nature; do not treat 10 minutes as the total task budget. At the limit, verify the scene and stop repeating the failed method; pursue supported recovery within existing authorization and report any remaining decision or missing prerequisite; never kill the process just because one wait expired.

When key information is missing, the owning agent investigates within authorization; consult the human for out-of-scope information or key inputs that cannot be obtained. For external platform work-item status and the like, trust an actual platform read — no speculative attribution about process or required fields; report exactly what the evidence shows. Deviation from the confirmed plan can be corrected and continued; when the plan itself is wrong in direction, on major decisions, or the scope changes, stop and hand to the human for judgment. Handle routine recovery within existing authorization; do not auto-create tasks for recovery.

Hand logins, identity, approvals, or upstream rejections straight to the human; switching tools or auto-approving parameters is not a way around approval. When login must be arranged in advance, read `auth.recurring_login_hint` from the host's `lbkit-agents.yaml`; without a reliable hint, check the actual login state — never infer a fixed expiry rhythm. Before resuming execution, confirm the original task is still authorized, the candidate and inputs are still valid, and monitoring is ready again.

## Cleanup Branch

When cleanup is explicitly requested, touch only approved sessions or resources; do not force-pick the first unchecked business item, and do not dispatch tasks along the way. The owning Sailor may delete a completed worktree within the consuming repository's applicable cleanup authorization, protecting deliverables and user changes; this grants no other permissions such as branch deletion. When an authorized integration (e.g. squash into `master`) finds uncommitted changes in the target worktree, save them as a named stash first and report its name; delete only the worktrees and branches registered for this run, and report unregistered directories instead of removing them. Retention, reuse, and cleanup of sessions and monitoring are judged by the model against open responsibilities and contextual value.

On abnormal shutdown or a human-requested termination, first save the handoff, open responsibilities, and recovery conditions. Record session closure, task failure, project cancellation, and delivery completion separately; managing a group does not automatically include cleaning up old services.

## Result Applicability and Recovery

Reconcile new human decisions with stale packages before dispatch: update affected order, environment, permissions and acceptance, recording what was superseded. Preserve explicit per-destination order and verify each destination separately; historical success elsewhere is not current completion. Complete the declared substeps for each destination before advancing to the next. Stop on any destination failure; do not advance to the next destination until the failed one is resolved or the human redirects. A result can be a study, event, document or operational change; use only its agreed delivery and evidence gates.

For a failed method, inspect the actual rejection and side effects, then attempt supported routine recovery within scope. A tool's generic error category is not more authoritative than its specific rejection. Distinguish a narrow retry from a broader replay with additional effects; widening side effects requires its own authorization. Do not turn every stall into a human choice or retry unchanged indefinitely.

Before closing resources, ensure source references and key conclusions are recoverable under the host record rules. This does not require copying raw materials into the coordination repository.

## Requested run metrics

Record run start/end/resume, human waiting/interruption, distinct human turns and applicable first acceptance/corrections in the existing bound Thinking using the [event contract](../../../docs/installable/coordination.md#run-event-and-close-out-metrics). Resume keeps the same run and counters. Captain records coordination facts; Sailor returns actual acceptance facts and later defect corrections. Do not archive raw trials or create a metrics sidecar.

At Stage/logbook 🎉, report exact scope, wall elapsed with waiting/interruption union, human interaction count/categories and first-pass numerator/denominator/rate. Use the read-only `skills/lb-push/scripts/run-metrics.py` helper for deterministic arithmetic; no event history or zero denominator gives explicit unknown/no-calculable-data, never invented success. A corrected delivery defect removes an erroneous first-pass pass even if rework later succeeds. Metrics do not complete human gates or create a checker role.
