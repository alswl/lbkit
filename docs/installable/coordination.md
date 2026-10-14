# Coordination Contract

## Logbook and responsibility boundary

The Logbook expresses Admiral's goal as an Overview, ordered Stages and tasks. A task owns a result and applicable completion conditions; it is not a transcript of business operations. Concrete business records and verification methods belong to their host repository. Captain maintains current responsibilities, dependencies, blockers, delivery entries and shared progress from the current Logbook.

A work package assigns Sailor the current task reference, inputs, scope/permissions, result, applicable completion conditions and report-back entry. It can be a message or existing host record. It is not a second scheduling checklist and does not require a file per dispatch. Task, package and continuing agent session remain separate objects, as defined in the task/session/resource distinction.

## Roles, authorization and returns — US2

Admiral is the human owner of goals, major tradeoffs, authorization and applicable human gates. Captain maintains the route, dependencies/owners, authorized dispatch/monitoring, return alignment, progress and coordination handoff. Sailor performs business implementation, investigation, testing, review and acceptance. Another Sailor may independently check a result when needed; this creates no separate acceptance role, default checker count or universal verification gate.

Plan confirmation is distinct from execution authorization. Existing authorization covers routine continuation, rework and recovery within its scope, without repeated per-step permission. A status, formatting or read-only analysis request dispatches no business work. An explicit newer Admiral decision supersedes the conflicting older condition only within its scope; record that change in existing Thinking and preserve unrelated constraints.

A Sailor return identifies the current Logbook/Stage/task/package, current result/revision, applicable inputs/conditions, acceptance outcome (passed, failed, incomplete or unknown), delivery entry, remaining responsibilities and limitations. It can be a message or existing host record. Captain verifies correspondence and readiness/control facts; Sailor performs original business observations and tests. A file, delivery link, bare done claim or runtime exit is insufficient. Changed inputs/task/result route concrete rechecking to Sailor within existing execution authorization; a status-only request cannot start that rechecking.

lb-update keeps reread (read-only default) and authorized refresh, with internal format/progress/close modes. Progress aligns applicable returns. Close reconciles goals, explicit human rulings, skipped/cancelled dispositions and open responsibilities. A task remains incomplete when its outcome is missing, conflicting, failed, incomplete or unknown. Human tasks remain subject to protected ownership: agents may record actual human work starting but do not complete, cancel or change the gate. All CLI writes retain the current `version_token` CAS protection.

Independent review, when required by a package, uses another Sailor and the same identified candidate. Candidate check rounds are finite and keep their used count across session switches and rework. No checker is manufactured for a task requiring no independent check; no resetting limits by splitting packages or changing tools. Human review/merge decisions remain distinct from Sailor acceptance and creation of a delivery entry.

## Authorized Git changes

These rules apply only to an already authorized commit/history operation; they grant no commit, push or history-rewrite permission. Business delivery commits belong to Sailor; Captain performs only authorized coordination-state handoff operations.

Git commit discipline for authorized agents: when working in the same repository as a human, always commit with `git commit -- <explicit path>` (pathspec) and self-check with `show --stat` afterwards to confirm no one else's files slipped in; committing without a pathspec sweeps up the human's staged in-flight content. The reverse trap is just as real: when the same file mixes in uncommitted lines from the owner, a pathspec commit takes the entire **working tree** version, dragging the owner's lines into the commit and afterwards writing back over the manually staged index. When you need to commit only your own lines, do index surgery: `git hash-object -w <sanitized content>` plus `git update-index --cacheinfo 100644 <blob> <path>` to stage precisely, then run `git commit` **without a pathspec** so the commit tree comes only from the index; afterwards use `git status` to confirm the owner's lines are still in the working tree. Before and after rewriting or repairing local history, `fetch` first and check the remote state of the target branch; never assert from session memory that "the remote doesn't have this branch / it was never pushed" — the remote may already have a same-name branch or a push made in the meantime, and missing it causes divergence.

## Parallel discovery — US2

At initial route reading, after each acceptance return and when waiting/blocked, Captain inspects actual input/output dependencies, human rulings, Sailor owners, mutable files and shared browser/service resources within the current route. Different repositories, worktrees or titles alone prove no independence.

Output one specific batch proposal with result/owner per package, input snapshot, read/write/resource isolation, convergence point and authorization status; or name the actual conflict/dependency. Already authorized batches proceed without repeated approval. Unapproved batches remain proposals while unaffected authorized work continues. No task splitting, reordering, scope expansion or human-gate bypass follows merely from discovering an opportunity. Passable human waiting requires the confirmed plan's explicit exception, independence and actual execution authorization. Scheduling preserves each package's compliant model/data boundary, isolation, visible monitoring and applicable acceptance return.

## Remote execution and Captain-managed handoff — US3

Cross-machine Sailor execution keeps the original Captain/Logbook scheduling responsibility. A package targets the named execution machine, approved directory and actual workspace/session, receives an actual Sailor acknowledgement and returns the current result to the original route. Captain performs dispatch/observation; business implementation and acceptance remain Sailor responsibilities.

Coordination handoff instead transfers current coordinating state and necessary results to a destination Captain main session. Captain directly manages authorized coordination operations rather than creating a business package for them. The [runtime adapter](../../skills/lb-push/references/execution.md) specifies separate locators, receipt, monitoring, session reuse and partial states for these two flows.

For handoff, record named source/destination machines, approved directories, matching workspace name and each end's actual workspace ID, coordination/result scope, permitted commit/push/ref operations and the endpoint. Then:

1. Compare both ends' refs, candidate identities, working/index changes, reliable rulings and outstanding packages.
2. Protect uncommitted work without reset/overwrite; synchronize/retrieve only authorized branches/state/results. Do not push main, publish or upgrade environments by implication.
3. Preserve reliable human rulings even when the destination copy is old. Ask Sailor to assess result applicability after subsequent input changes; missing rulings remain unknown.
4. Prepare the same named workspace using the destination's own actual locator. Execution/monitor entries explicitly use registered cwd. An inherited unrelated root entry stays unused and closes only after safe non-use/no-input/no-activity confirmation.
5. Verify the receiving Captain's actual main session obtained the current handoff and reread location; record its current gate and open responsibilities. Resource creation, matching names or a side-session/tool delivery receipt alone do not complete the handoff.

This is an authorized coordination exception, not permission for Captain to perform business setup/content production or access undeclared machines/directories. Existing authorization covers routine steps only; broader goals, machines, directories and operations still require Admiral's decision. Preserve reliable human rulings and pending gates during either flow.

## Human delivery/readiness — US4

Sailor checks the complete changed-file inventory before commit and again at handoff against host layout, content, required bindings and indexes (including Article/Prompt/Thinking/Source where relevant), and includes the outcome in the delivery return. A successful parse/build does not establish host conformity; missing checks leave delivery incomplete.

Distinguish original business sources, formal deliverables and local process material by purpose and host ownership. Renaming a confirmation sheet, per-round decision sheet, execution log or validation output does not make it a formal source. Authorized untracking must preserve human annotations and recovery pointers and check local ignore behavior; it grants no permission to delete local files. The host governs retention and cleanup.

When the confirmed delivery requires a PR, Captain aligns that return and reads control facts: actual current PR/head/accessibility and recipient entry. Local-only results, an old PR or an active prohibition are not a ready merge gate. PR creation belongs to Sailor when authorized; merge/human approval remains a distinct Admiral decision. Preparing a PR does not authorize main-branch pushing, merge or unrelated changes.

For explicit branch-only delivery, Captain aligns the actual branch/ref/candidate and usable review entry against the Sailor return. Uncommitted working-tree changes must be identified separately from branch HEAD. This choice creates no PR requirement or commit/push/merge permission; an existing PR-required gate changes only through an explicit Admiral ruling.

For either delivery mode, hand over the exact verified destination. Resolve a local entry against its known repository/workspace root with a read-only filesystem operation; use the returned path rather than reconstructing directory names in prose. Use the service-returned URL for a PR. Check the literal link destination intended for the final response against the current candidate, including after any path or URL conversion; having read the original relative file does not verify a newly constructed absolute link. Copy that checked destination into the handoff unchanged. An inaccessible or mismatched destination leaves the handoff incomplete; this entry check is a control fact, not business acceptance.

For authorized terminal review, Captain coordinates/opens the host review entry and reads back its first usable view. Sailor queries actual editor/Markview state before layout and checks content/rendered structure. Captain must not independently compare candidate content, recount tables/headers or recompute rendered budgets while calling it return alignment; correspondence uses current identity and the applicable Sailor checks/outcomes. Protect focus, unsaved buffers and unsent text; use an independent safe preview or report the gap when the current buffer cannot be checked safely.

Table sections use actual rendered window width/height, including sidebars, number/sign/fold columns, borders, padding, CJK/emoji and continuation rows. Split by semantic or contiguous-numbered ranges, repeat full headers and preserve all candidates/quotations/order/answers. Each table/correction section has nearby scoped feedback and clear heading spacing. Existing work-package defects are repaired before a corrected return; reporting framework feedback alone is not repair or acceptance.

## Metrics and durable records — US7

Requested run lifecycle, human-interaction and first-acceptance facts live in the Logbook's existing bound Thinking using the run-event rules below. Captain records coordination facts and reports scoped elapsed time, interactions and first-pass success at 🎉. Sailor returns applicable first acceptance and subsequent defect corrections. Resuming a session preserves the run and counts; cancelled/pending work, insufficient history and zero denominators cannot become fabricated success.

Source, result, handoff and recovery entries preserve the host's existing record ownership. The Logbook is not a default archive of raw outputs, temporary process sheets or detailed business validation. No framework evidence index or mandatory parallel record system is introduced by the return or metrics protocols.

## Host integration

Resolve host tools/skills actually available for runtime, review, document binding and business delivery. The host owns its AGENTS/config/Logbook and no new obligations are silently injected during install. No inferred Herdr/Markview commands, profile takeover, hidden monitor substitute, new record backend or auto-install is introduced. Missing required capabilities are readiness gaps. Model/deployment, isolation, visible monitoring, bounded checks and authorization invariants remain from existing host rules.

## Run event and close-out metrics

### Storage and helper

Use the current logbook's uniquely bound Thinking via the host document adapter. A compact fenced section labelled `lb-run-events` holds one JSON object per line, optionally across multiple event sections. This is part of existing Thinking, not a new file/source index/metrics backend. Record only needed events; do not archive original observations to substantiate every event.

Read-only helper:

```sh
python3 .lbkit/skills/lb-push/scripts/run-metrics.py   --root HOST_ROOT --thinking THINKING_RELATIVE_PATH   --run-id RUN_ID --scope logbook
```

For a Stage, --scope carries the exact Stage title. The helper resolves the Thinking path within approved --root, reads only that file and emits JSON to stdout. It does not infer bindings, scan transcripts, install tools, fetch networks, write/correct events or create any files. No usable event history returns unknown values with explicit coverage instead of fabricated totals. Bad arguments/events fail with exit 2; path/read failure with exit 3; valid complete/partial/unknown metrics return exit 0.

### Event fields

Every event has stable run_id, event_id, type, scope, at (timezone-qualified ISO 8601 or null) and origin/reference. scope is logbook or an exact Stage title. Optional fields are package_id, human_turn_id, interval_id, category, outcome, first_pass, corrects, reason and coverage (complete/partial/unknown). Missing data is represented explicitly, not as zero or a guessed timestamp.

| Event type | Additional fields / meaning |
| --- | --- |
| run_start / run_end / run_resume | Continuous run lifecycle; resume does not reset counts or change start |
| scope_start / scope_end | Stage reporting endpoints; logbook uses run endpoints |
| wait_start / wait_end | Same interval_id; planned human waiting |
| interruption_start / interruption_end | Same interval_id; outage/forced interruption |
| human_turn | Stable human_turn_id; one mutually exclusive gate/additional/recovery category |
| package_first_outcome | Stable package_id; passed/failed/incomplete/unknown and first_pass when known |
| package_correction | corrects an existing first-outcome event; reason and effective first_pass/outcome |

At equal event_id an identical replay is deduplicated; differing content is a conflict reported rather than summed. Invalid/cyclic corrections or duplicate initial outcomes for a package are errors/unknowns, not silently chosen successes. A correction of a delivery defect cannot erase task rework and regain first-pass success solely because a later candidate passes.

Each measured scope supplies truthful history coverage. A helper cannot prove that unrecorded events never occurred; partial/unknown coverage limits the reported total. Missing timestamps do not imply zero-duration events. Stage-scoped summaries include events attributed to that scope and intervals clipped to its endpoints; run-wide totals deduplicate event/turn/package identities across scopes.

### Elapsed time

Total wall elapsed = scope_end − scope_start (or run_end − run_start for logbook). Future/inverted endpoints and missing boundaries are unavailable or invalid, not negative/zero totals. Open runs are not reported as completed 🎉 totals.

Report known waiting duration and known interruption duration separately. Also compute the union of all clipped waiting/interruption intervals to avoid double counting overlaps. Remainder = wall elapsed − interval union only when both endpoints and interval coverage are sufficient. It is remaining wall time, not CPU/agent compute time. An open interval or missing pairing makes the affected total unknown, with known intervals optionally shown as a labelled lower bound.

### Human interactions

Count distinct submitted human turns affecting this run, not individual answers, tool calls, agent-to-agent messages or skill switches. Categories are planned gate decisions, additional clarification/direction and connection-only disconnection/resumption. A turn containing a planned decision is a gate; connection-only continuation is recovery; other task-affecting turns are additional. Retain secondary detail without double counting. Unknown identities/history yield scoped known counts plus unknown total where appropriate.

### First-pass success

Denominator = packages with an initial applicable acceptance outcome; pending/unexamined and cancelled-before-first-acceptance packages are excluded. Numerator = those passing that initial acceptance without task rework, after applying explicit corrections. An initial incomplete/unknown acceptance outcome is not a pass; distinguish never examined packages from examined packages with unresolved findings.

A later human-reported delivery defect supplies a package_correction linked to the original outcome, removing its erroneous first-pass classification. Later success after rework does not improve the initial-pass numerator. This metric neither creates a mandatory independent checker nor completes a human gate. Zero denominator produces unavailable rate; insufficient historical coverage prevents a fabricated whole-run percentage.

### 🎉 output

Captain reports exact Stage/logbook scope, total elapsed (and wait/interruption/union breakdown), distinct human turns by category and first-pass numerator/denominator/percentage, or explicit unknown/no-calculable-data values. Link to the bound Thinking entry, not a newly created report. An applicable human gate or unfinished responsibility remains visible; metrics never turn cancellation or cleanup into successful delivery.
