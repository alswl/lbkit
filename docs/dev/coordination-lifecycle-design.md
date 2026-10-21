# Coordination lifecycle, close-out and retrospective design

Status: implementation design. The atomic-operation boundary below supersedes broader proposals later in this document. Implementation does not authorize migration, external publication, or changes to human-owned goals and tasks.


## Atomic CLI boundary

Skills own decisions and sequences; the CLI owns deterministic observations and single-file mutations. A command succeeding proves only its declared effect, not completion of a workflow or human approval. Do not implement a multi-file scaffold, retrospective or session-cleanup transaction.

| Operation | CLI | Skill responsibility |
|---|---|---|
| Maintain a template | show/check; create or replace one complete candidate with token, preview and CAS | lb-workflow establishes semantics, protects goals/gates, reviews the diff and separately records its source |
| Generate an instance | render fills slots without writing; instantiate validates at the destination and creates only that file | lb-scaffold confirms inputs, selects the output, creates/verifies adapter bindings separately and reports partial setup honestly |
| Record lifecycle/events | state-set updates one log; run record appends one readable, idempotent event to Thinking | plan/push/update determine authorization, facts, event attribution and recovery |
| Close out | audit/metrics/closeout report saved evidence | lb-update aligns actual returns; authorized push performs live checks and cleanup |
| Retrospective | scan one fixed ref; record/update one ledger | lb-retro selects scope, groups sources and judges adoption |

Workflow replace does not edit companions, indexes, tasks in existing instances or goals on the caller's behalf. Its structural validation is not semantic authorization. Skills author new workflow candidates; workflow create publishes one candidate into an already prepared approved docs directory, without overwrite. This adds no directory-bundle generator. Existing template syntax with unclear slot boundaries must be maintained explicitly, never guessed by scaffold.

Render preserves a declared fenced YAML front matter (including workflow/prev-run) and all prose after the contiguous directory list; a dedicated <WORKDIRS> placeholder is also supported. Placeholder substitution is one pass. Instantiate checks deterministic issues at the output location before publishing a complete file without overwrite. Structural marker checks are labelled as a subset, not semantic or real-instance certification.

Retro reports the selected snapshot and dirty exclusions, explicitly stating that other branches/worktrees were not inspected; automatic cross-branch discovery is deferred. Closeout retains the current executor-return requirement; a second CLI runtime-cleanup inventory is deferred to avoid duplicating skill responsibility. Offline runtime bindings never establish live ownership. These scoped decisions replace the broader discovery/cleanup expectations below.

## 1. Design decisions

Keep lifecycle management in the existing skills. Do not introduce an `lb-lifecycle` skill. Add `lb-retro` for cross-logbook retrospective work on the host's main branch. Make the CLI responsible for deterministic generation, validation and guarded writes; skills own interpretation, authorization and evidence alignment; Sailors own business observations.

The main Logbook has exactly one CLI-owned status line. Task bodies show current results and delivery entries, not a running transcript. Bound Thinking holds significant decisions, recovery pointers and structured coordination events. Do not archive polling output or duplicate business evidence.

Default new execution packages to Captain and Sailors on the same machine. Preserve explicitly authorized remote work; changing this default does not migrate or stop existing sessions.

## 2. Responsibility and invocation

| Concern | Accountable skill / Captain action | Sailor contribution | CLI responsibility |
|---|---|---|---|
| Initial lifecycle | `lb-plan` / `lb-scaffold`: draft and confirmation basis | None required | Initialize metadata and generate status |
| Start, wait, resume | `lb-push`: verify authorization and reconcile current runtime | Receipt and progress | Record transitions/events and sync status |
| Pause, terminate, close | `lb-update`: apply explicit decisions or align close-out returns | Final results and open responsibilities | Guard metadata, prepare close-out report, sync status |
| Observe | `lb-status`: report recorded/live facts | No new work | `log state`, counts and stale-state diagnostics |
| Template maintenance | `lb-workflow`: design and revise an authorized template | Relevant instance findings | Catalog, contract check, render preview and provenance |
| Delivery accessibility | `lb-update` aligns checks; `lb-push` dispatches checks when execution is authorized | Test actual delivered entry and replacement after cleanup | Enumerate links and register scoped observations |
| Metrics | `lb-push` records during execution; `lb-update` summarizes at Stage/project close | First outcomes and corrections | Validate events, deduplicate and calculate |
| Cross-project improvement | `lb-retro`: consolidate on host main branch | Existing usage and failure returns | Incremental discovery, stable issue records and evidence links |
| Runtime targeting | `lb-push`, `lb-takeover`, `lb-handback` | Current session identity and relinquishment | Resolve and verify registered runtime bindings |

Switching skills does not create another approval gate. An update-only request records missing checks; it never dispatches Sailors implicitly.

## 3. One generated status line

Examples:

```text
> 状态：🚧 进行中 · Stage 02 · 待人工
> 状态：⏸ 暂停
> 状态：⛔ 已终止
> 状态：✅ 已完成
```

The line contains lifecycle, the current Stage identifier when applicable, and at most one progress qualifier. No full task text, URLs, runtime IDs, counters, timestamps or narrative history. Details remain available from `lb log state --json` and the owning task. Long stage titles are not copied into the line; where no short identifier exists, omit it rather than inventing a new stage name.

Extend existing `lb log sync LOG --expect-version TOKEN --dry-run` to create or replace this single owned line. All lifecycle transitions call the same renderer and update metadata plus the line in one file mutation. Ordinary status observation only writes when permitted. Existing free-text status and human commentary are preserved; migration previews identify them and must not silently erase or reinterpret them. Duplicate owned lines are an error.

### State model

Persist only lifecycle facts: `draft`, `ready`, `active`, `paused`, `completed`, `terminated`. `ready` means the route is confirmed, not that execution is authorized. Waiting for a person, a preflight gate, and a blocker are progress conditions, not separate project lifecycles.

Store current lifecycle in a reserved document-level metadata comment, with decision/reference, observation time, run identity and applicable document/candidate references. Do not create a second project database. Transition history belongs in the bound Thinking event stream, with stable event IDs. A missing history write is a recoverable partial operation, not a reason to apply the transition twice.

Proposed CLI: `lb log state set LOG --lifecycle VALUE --basis REFERENCE --expect-version TOKEN [--dry-run]`. Keep existing `lb log state LOG --json` compatible, adding subcommand dispatch without removing the old form. If that grammar cannot be made unambiguous, select a distinct mutation command during implementation and document it before migration.

| Transition | Skill | Required basis |
|---|---|---|
| New → draft | plan/scaffold | Human-supplied goal or protected placeholder |
| draft → ready | plan/scaffold | Confirmed route and directories |
| ready → active | push | Execution authorization and actual start |
| active → paused | update, called from push if appropriate | Explicit human pause |
| paused → active | push | Explicit resume and fresh reconciliation |
| nonterminal → terminated | update | Explicit termination; remaining responsibilities retained |
| active/ready → completed | update close | Applicable results, human decisions and close-out reconciliation |
| completed/terminated → nonterminal | plan/update then push | Explicit reopening/new scope decision; no counter reset |

`log state` reports inconsistencies, such as new unfinished tasks under completed, rather than continuing to display an apparently valid completed result. CLI validation checks supplied references and deterministic conditions, not authenticity of human authorization or business success. The skill remains accountable for those judgments.

Existing 🔮 blocks advancement and normal writes. Proposed narrow exception: recording pause/termination or refreshing the generated status may preserve the gate verbatim; it may not clear the gate, resume, accept tasks or complete the project. This is an explicit contract change requiring behavior tests, not a bypass flag. Until implemented, keep the existing refusal.

Do not derive lifecycle from process liveness, unchecked-task counts alone, or old prose. Unknown legacy lifecycle stays unknown until reconciled.

### Reduce task history

Use existing `task note --kind 状态 --replace-line` for one current Agent status. Keep a small number of current artifact entries when they represent distinct deliverables. Preserve human text and annotations. When several old statuses exist, propose the exact consolidation and retain necessary dated decisions in Thinking; do not bulk-delete based on keywords.

New updates no longer append routine started/retried/waiting messages. CLI `log check` reports competing current annotations as a maintenance notice, not as proof of invalid acceptance.

## 4. Workflow management

Keep Markdown templates in `workflows/<name>/`; keep the existing three slots and human gates. Promote the reusable `lb-workflow` contract into the shared skill set; preserve host-specific rules as host policy. Existing local copies must be detected by the installer, never overwritten silently.

Proposed commands:

| Command | Result |
|---|---|
| `lb workflow list/show` | Discover templates and show applicability, source and validation coverage |
| `lb workflow check NAME` | Check template section, slots, rulings, placeholders, skill syntax and relative links |
| `lb workflow render NAME --input-file FILE` | Read-only generation preview; no instance or index write |
| `lb log create PATH --from-workflow NAME --input-file FILE` | Create-only application of the reviewed render, with template token and adapter preflight |
| `lb workflow diff LOG` | Compare the pinned template provenance with the current template; report only |

Use a content digest for template identity, not an automatically bumped release number. Instance provenance records workflow path, template digest, source revision when committed, and slot inputs. Keep this outside the visible status line. The Markdown template remains authoritative; a catalog is derived, not a second editable copy.

`lb-workflow` owns semantic template edits; CLI renders/checks structure and refuses missing slots rather than inventing tasks. `lb-scaffold` owns instance creation and existing mind-forge bindings. Instantiate must detect partial companion/index creation, preserve created files and return a recovery plan; it must not claim an atomic transaction across Git/Markdown/mind-forge. Retry verifies matching bytes before reuse.

Template check does not certify successful real use. Record contract validation and instance validation separately. A completed instance is not automatically a valid template example, especially if its human gates or exceptions differ.

Common close-out behavior belongs to skills and CLI, not repeated boilerplate tasks in every template. Domain deliverables and independently owned cleanup remain explicit approved tasks. Never create hidden completion criteria for old completed tasks. New templates explain these checks within their actual delivery criteria.

Migrate templates individually: inventory → proposed semantic diff → authorized edit → contract check → next real instance. Do not change existing instance goals, task order or gates when their template changes.

## 5. Accessible delivery at close-out

Captain is accountable for the close-out inventory. The owning Sailor tests each actual business delivery entry using its authorized filesystem, browser or service CLI. Captain aligns the candidate, target and returned observation, and may open the entry to verify handoff readiness. A generic HTTP success is not proof that the intended artifact is visible.

Extend existing `lb log links record-check` rather than build a downloader or authentication broker into lbkit. Currently it records offline observations for HTTP(S) occurrences; extend it to local and machine-qualified remote entries. Proposed `lb log links audit LOG` enumerates required delivery links, their task/candidate, observation time, machine, outcome and applicability. It performs local existence checks only inside permitted roots; external/remote targets require supplied observations, never automatic SSH or credential discovery.

Differentiate delivery links from background references. Only required delivery entries participate in delivery readiness; an unavailable historical source is reported without blocking unrelated completion. Observations carry accessible/unavailable/retired/unknown results and access conditions without credentials or signed URL secrets. Target or candidate changes invalidate the matching observation. A verification timestamp is not a permanent availability guarantee.

Check twice where cleanup changes locations: before cleanup verify replacement and recovery locations; after cleanup verify the final entry. Failure leaves the original delivery/cleanup responsibility open. Do not invent a new task or silently delete evidence to make an audit green.

`lb-update close` consumes this inventory. `lb-push` obtains missing Sailor observations within existing execution authorization. Status-only/update-only requests report the exact gap and owner. No new link-auditing skill is needed.

## 6. Run metrics and close-out

Promote the existing `run-metrics.py` implementation into shared services with compatibility for historical event blocks. Proposed CLI:

```text
lb log events record LOG --input-file EVENT --expect-version TOKEN [--dry-run]
lb log report --view metrics LOG --scope stage|logbook --json
lb log report --view closeout LOG --scope stage|logbook --json
```

Events stay in uniquely bound Thinking. Record validates event identity, actual timezone-qualified time, source, run/package identity and coverage. It uses the Thinking file token, not the Logbook token as a substitute. Identical retries are idempotent; conflicting same-ID events fail. Events are recorded at start/resume, wait/interruption boundaries, human turns and first acceptance/correction, not reconstructed only at close-out.

Captain records coordination events through push/update. Sailor returns business outcome and elapsed facts; Captain does not infer elapsed execution from token counts or idle status. Preserve the same run across recovery and the same package across rework. Parallel intervals use a union for wall-time calculations; do not add durations from concurrent packages as elapsed time. Report actual net execution only where observed; otherwise label the residual as elapsed time excluding recorded waits, not CPU or net work time.

Closeout is a read-only aggregation: lifecycle and checklist dispositions; required delivery-link inventory; runtime/cleanup open responsibilities; metrics and coverage. It never checks boxes, sends messages, closes terminals or declares business success. `lb-update` makes the close decision from this report and applicable returns, then records it through guarded commands. Stage completion retains its checklist semantics; unknown metrics are reported, not an implicit new Stage gate.

The close-out reply includes scope, completed/cancelled/open counts, elapsed/wait/interruption coverage, human interactions, and first-pass numerator/denominator. The top line remains short. A compact snapshot may be recorded in Thinking with its input event digest; the live report is recalculated if events change. No independent metrics file is required.

## 7. Master-level lb-retro

Add one new skill: `lb-retro`, for cross-logbook learning on the host's configured main branch (default `master`). It does not replace per-package recording and does not become a compulsory task or human gate in every project.

### Who and when

1. During execution, Sailor returns actual skill usage, failures, workarounds and evidence references. Captain records material facts promptly via push/update. Major direction or capability issues go to the human when discovered, not at retrospective time.
2. At close-out, update records concise lessons and remaining feedback responsibility in existing Thinking. It need not perform repository-wide synthesis.
3. When the human invokes retro, a retrospective Captain reads a fixed main-branch snapshot over a chosen period or since the last checkpoint. It groups repeated findings, evaluates proposed adoption, and produces one reviewable summary. A weekly run is a recommendation, not an installed scheduler.

If the current checkout is not on the configured main branch, inspect that ref read-only; do not checkout, stash, pull, merge or commit automatically. Write application requires an already suitable authorized main-branch workspace. Dirty unrelated files remain untouched; concurrent edits to a target invalidate its token.

### Records and CLI

Use one host-owned feedback ledger with stable IDs, readable Markdown and small structured metadata blocks. Keep detailed sources in their original Thinking records. Existing skills/lbkit ledgers may initially remain separate and be federated by the CLI; later consolidation is an explicit migration, not deletion of solved records.

Proposed commands: `lb feedback scan --since DATE --ref master`, `lb feedback show ID`, and guarded `lb feedback record/update`. Scan uses source revisions and stable finding IDs, includes merged Thinking/feedback changes and distinguishes new business events from late backfill. Repeated scans do not create duplicates. Persist a checkpoint only after findings are durably recorded; checkpoint stores the inspected revision, not just a timestamp. Missing/unmerged local returns are reported as outside snapshot coverage, not silently consumed.

Each finding has source occurrences, classification (skill defect, usage failure, workflow defect, CLI limitation or new requirement), owner, decision, implementation reference, adoption references, verification evidence and deferred/rejected reason.

Keep three dimensions separate:

- Disposition: proposed / accepted / deferred / rejected.
- Implementation: not-started / implemented / verified (with exact scope).
- Adoption: instance references and observed outcome; no invocation inferred from a planned skill annotation.

Reuse `lb skill extract` for declared skills and `lb skill history` for available actual-call evidence. Session scans remain limited to authorized paths/machines; ambiguity stays unknown. The initial retro version relies primarily on saved returns, so it does not require access to old session files. CLI assists matching and deduplication; Captain decides semantic equivalence and usefulness. No automatic global skill rewrites, issue publication or task creation.

Accepted host-rule, workflow or shared-skill improvements go to their existing authorized maintenance path. Implementation still requires suitable authorization; retro itself may produce proposals and maintain its authorized ledger. The retrospective report separates local adoption, upstream implementation and behavioral verification. Retain closed findings so adoption rates have stable denominators and dates.

## 8. Same-machine runtime and stable Herdr identity

Improve both lbkit and the skill adapter. `lb agent bind/inspect/send/close` stores, observes and controls a dispatch-bound machine, workspace ID, tab ID, pane ID and actual agent/session identity. Display names are for human navigation. List position, tab ordinal and abbreviated IDs are never persisted as action targets.

Store the minimal binding in existing Thinking; live status is an observation, not authoritative project acceptance. Reuse current task/package/dispatch identity; do not create a second task queue. The CLI adapter validates supported Herdr structured interfaces before claiming it can resolve a target. Where full stable IDs are unavailable, return a capability gap rather than inventing identifiers.

Creation remains under push using actual Herdr returned IDs. Before prompt, stop, close or takeover, resolve and verify the current recipient, input line, ownership and package. A mismatch refuses the dependent operation; no fallback to the first match or a numeric index. Agent-not-found may be reconciled by a matching live pane/session, never by blindly creating another executor. A cached mapping saves repeated discovery but cannot skip pre-action verification.

Initially the lb CLI supplies bindings and read-only validation; mutation stays with the skill using Herdr's supported API. This avoids a second runtime orchestrator. The operation sequence should become a single reusable adapter routine, with quoted argument transport and post-action readback, rather than copied shell fragments in every skill.

Same-machine default belongs in host configuration/policy and skill selection. It is neither a deployment classification nor permission to use an external model. Exceptions require an already authorized remote directory and reason. Existing remote packages remain intact; no cross-machine browser credentials are moved.

Captain raises core unknowns at planning/preflight and reports concrete capability gaps when encountered. Routine repair stays with the authorized executor. Ask one compact decision question with facts, impact and recommendation; do not defer known blockers until timeout or convert every technical detail into human approval.

## 9. Implementation order and acceptance

The following are proposed implementation batches, not new project todos or execution authorization.

1. Current status and lifecycle: metadata/parser, shared renderer, guarded transitions, skill integration and narrow gate semantics.
2. Close-out: link inventory/observation extension, shared run metrics/event writer, read-only closeout report.
3. Workflow management and retro: CLI template contract/provenance first, shared workflow skill installation, incremental retro ledger and main-branch workflow.
4. Runtime binding: read-only adapter capability verification, exact identities and same-machine selection integrated into push/takeover/handback. Apply the same-machine/no-index skill guidance early; do not wait for runtime CLI implementation.

Target modules: existing `models.py`, `document.py`, `views.py`, `edit.py`, `storage.py`, commands/services for logbook/links/skills; new focused workflow/run/retro/runtime services where necessary. Reuse guarded storage rather than write independent file editors. Extend installable lifecycle, coordination, format, configuration and CLI contracts alongside skills; update the installer manifest for new shared skills. Preserve consumer copies on name collisions.

Required tests include:

- One owned top line after repeated sync; unrelated human content preserved; stale tokens and duplicate metadata refused.
- Terminated logs retain unchecked history without showing an actionable next task; paused logs never resume from a status query.
- Completion inconsistency after new human tasks is visible; no automatic human checkbox changes.
- 🔮 remains intact during allowed terminal metadata updates; ordinary advancement still refuses.
- Template rendering preserves order and gates; incomplete slots fail; template changes never mutate instances; partial adapter writes recover without duplication.
- Final link moved/deleted or candidate changed invalidates its observation; background links do not become hidden completion gates; remote unknown is not available.
- Event retries, overlaps, interrupted runs, unknown historical counts and later first-outcome corrections calculate honestly.
- Retro rerun deduplicates; main-branch snapshot excludes unmerged findings explicitly; implemented does not mean verified or adopted.
- Renamed/reordered Herdr tabs still resolve by actual identity; reused pane/session mismatch refuses action; unrelated human resources remain untouched.
- Skill behavior trials cover delivery, suspension, termination and retrospective workflows, separately from unit tests and template contract checks.

Migration is opt-in per host/logbook/template. Keep old readers and metrics helper compatible while introducing new commands. No automatic schema/package/skill version bump; compatibility and release numbering remain a human decision. No commit or push is part of this design.
