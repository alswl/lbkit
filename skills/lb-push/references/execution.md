# Execution, Review, and Recovery

Read before dispatching, resuming, or authorized cleanup. This file defines the operating process; tool commands come from the selected adapter. The [Repository Boundaries](../../../AGENTS.md) and the [Configuration Contract](../../../docs/configuration.md) always apply.

## Runtime Adapter Contract

Before execution, verify the selected adapter provides: explicit executor targeting, preserved human focus, an isolated execution space, task submission with receipt confirmation, independent visible read-only status waiting, and report-backs tied to this dispatch. Report the specific gap if any is missing; never fabricate capabilities or pass polling off as monitoring.

The [Herdr Adapter](herdr.md) is currently provided and must be read and followed only when runtime.adapter=herdr. Other environments must supply reliable adapter documentation and capability evidence; no automatic switching. The visible monitoring requirement declared by the host repository cannot be configured away.

Existing sessions that meet requirements may be reused; do not restart just to re-parameterize. Only new or replaced processes require parsing a launcher; choose from the declared candidates per need, replacing command and args atomically without mixing in old parameters. Reuse still requires verifying the actual model and data boundary before sending material; a failed launch does not authorize calling some other model directly.

## Dispatch Loop

1. Locate the work package, executor, authorization, and isolated space; confirm inputs and dependencies are ready, and that release prerequisite evidence within the original scope has been checked or explicitly scheduled.
2. Hand the full task to the owning executor, obtain proof of receipt, and observe real status. Report the launch gate, task receipt, and business execution separately.
3. After receipt, establish independent visible monitoring tied to this dispatch and verify monitoring readiness. A successful run with failed monitoring is a partial completion; fix the monitoring, and do not resubmit the business task.
4. Each status wait is at most limits.wait_seconds; this is not a task execution deadline, and one expired wait never justifies killing the executor. Immediately after each wait, read the latest status and output: if `idle`, `done`, or `blocked`, stop waiting and handle the report-back or blocker; if still `working`, report the new command, artifact, or evidence, or the concrete basis for calling it stalled. Never repeat waits without refreshing status and output, and never treat one `working` snapshot as continuous operation. Keep progress human-visible.
5. Hand received report-backs to lb-update's evidence process. Tie gaps to the original package; after acceptance, re-read the logbook and move to the next item within the existing advancement authorization; stop at an explicit single-item or batch endpoint, a human gate, or a severe blocker — acceptance itself is not an authorization expansion.

## Independent Checks and Finite Rework

When independent checks are needed, the implementer first fixes a candidate, then the same identity goes to different checkers. Checkers do not modify deliverables; they return pass, fail, or evidence-linked gaps. Each time a candidate goes to an independent check counts as one round; the first round counts against limits.review_rounds; multiple checkers reviewing the same candidate are one round.

Return only relevant gaps to the implementer, and re-verify affected results with the new candidate; preserve rounds already used. Stop and hand to the human at the cap, when required authorization is missing, or on major tradeoffs — never dodge the cap by switching skills, restarting sessions, or splitting new packages. `review_rounds` bounds the rounds a candidate goes to independent check; human review rework rounds on the same PR (review → fix → CI → respond) do not consume that quota, but when the same kind of review repeats without substantive convergence, report to the human owner per the stalled rules instead of responding indefinitely.

## Blockers and Recovery

Before retrying, verify existing candidates, external state, and unfinished operations via the control plane or the owning agent to avoid duplicate side effects. Set applicable tool timeouts for CLI, MCP, or network calls; limits.wait_seconds does not directly cap total business command time.

Judge timeouts per the task's nature, usually with 10 consecutive minutes without effective progress as the limit; effective progress means new facts, command results, artifacts, or evidence — repeated status text does not reset the clock. For builds or tests of known duration, set deadlines per the task's nature; do not treat 10 minutes as the total task budget. At the limit, verify the scene, stop retrying, and report to the human; never kill the process just because one wait expired.

When key information is missing, the owning agent investigates within authorization; consult the human for out-of-scope information or key inputs that cannot be obtained. For external platform work-item status and the like, trust an actual platform read — no speculative attribution about process or required fields; report exactly what the evidence shows. Deviation from the confirmed plan can be corrected and continued; when the plan itself is wrong in direction, on major decisions, or the scope changes, stop and hand to the human for judgment. Handle routine recovery within existing authorization; do not auto-create tasks for recovery.

Hand logins, identity, approvals, or upstream rejections straight to the human; switching tools or auto-approving parameters is not a way around approval. When login must be arranged in advance, read `auth.recurring_login_hint` from the host's `lbkit-agents.yaml`; without a reliable hint, check the actual login state — never infer a fixed expiry rhythm. Before resuming execution, confirm the original task is still authorized, the candidate and inputs are still valid, and monitoring is ready again.

## Cleanup Branch

When cleanup is explicitly requested, touch only approved sessions or resources; do not force-pick the first unchecked business item, and do not dispatch tasks along the way. A completed worktree may be deleted by the owning executor agent, protecting deliverables and user changes per the root rules — this grants no other permissions such as branch deletion. Retention, reuse, and cleanup of sessions and monitoring are judged by the model against open responsibilities and contextual value.

On abnormal shutdown or a human-requested termination, first save the handoff, open responsibilities, and recovery conditions. Record session closure, task failure, project cancellation, and delivery completion separately; managing a group does not automatically include cleaning up old services.
