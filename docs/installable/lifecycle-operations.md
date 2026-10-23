# Lifecycle, close-out and learning operations

The [domain command contract](domain-commands.md) defines the canonical object routes, task/dispatch lifecycles and workflow availability. All commands below use the public concept-oriented routes; new templates start in draft.


These operations extend the existing lb skills; the host root AGENTS.md and current authorization govern access and writes. No command proves human authorization or business success. The CLI performs deterministic work; Captain aligns evidence and decisions; Sailor performs business observations. Commands never commit, push, publish, control browsers or switch branches.

## Current facts and one page status

The only new skill is [lb-retro](../../skills/lb-retro/SKILL.md). Lifecycle management stays in plan/scaffold, push, update and status.

- plan/scaffold record draft, then ready after route confirmation. Ready does not authorize execution.
- push records active on actual authorized start, and resumes only with the applicable explicit resume instruction.
- update applies explicit pause/termination, reconciles reopening, and records completion after applicable returns and human decisions. A terminated logbook keeps unfinished history without scheduling it.
- status reads these facts and may sync only when writing is authorized. Observation does not resume work.

`lb log state-set LOG --lifecycle draft|ready|active|paused|completed|terminated --basis REFERENCE --expect-version TOKEN` previews with `--dry-run`, then writes lifecycle metadata and one short page status together. It never changes a task checkbox, heading text or goal. Completed requires a nonempty settled checklist; the caller still verifies results and human decisions. Completed with new unfinished tasks is reported inconsistent by state. Normal task writes stop under paused/completed/terminated until an applicable transition; no status query reopens a project.

`lb log sync` creates a missing compact status line. Legacy lifecycle is unknown until explicitly reconciled; a missing checkbox does not prove an active project. Legacy human status and commentary remain untouched; state-set refuses to overwrite them, requiring an explicitly authorized local migration first. Repeated sync must preserve one line, never append a second. New lifecycle pages show only lifecycle, short Stage identifier and at most one qualifier; detailed tasks and runtime IDs stay out of that line. During unresolved 🔮 only state-set pause/termination may update its metadata and generated line while preserving the gate. Other existing write refusals remain in force.

At each accepted return, keep a concise current task result, usable artifact entries and remaining responsibility. Use `task note --kind 状态 --replace-line` for an existing Agent current status. Historical conflicting statuses require a protected local consolidation, preserving human comments and significant decision/recovery references in Thinking. Do not append polling, every retry, timestamps or model counters to main tasks. Thinking keeps significant events, not a full terminal transcript.

## Who checks delivery links

`lb-update` owns delivery/close-out reconciliation. `lb log links audit LOG` inventories artifact-annotation links as required delivery entries; background links remain references. Actual business checks belong to the owning Sailor, dispatched via lb-push only within execution authorization. Update-only reports a missing check without dispatch.

Sailor uses the appropriate approved filesystem/browser/service CLI and returns the observed candidate, entry, time, access conditions and result. Captain checks correspondence and readiness. Register observations with existing `lb log links record-check` (now supporting local/remote targets as well as HTTP(S)), current token, dry-run and write. Put non-secret machine/access conditions in `--basis` and identify the candidate in `--result-identity`. `verified`, `unavailable`, `revoked` remain the outcome values. This stores evidence; it does not fetch or authenticate. Never include credentials or signed URL secrets.

Audit probes existence only within the host root. Existing local bytes do not prove content or candidate correctness; outside-root and remote links need supplied observations. Changed target/context/acceptance/artifact invalidates the matching observation. Check replacement locations before cleanup and final delivery locations after cleanup. Keep the original delivery/cleanup responsibility open when its required entry is unusable; preserve recovery material. Historical reference failure alone is not a new gate.

## Run events and close-out

Captain records coordination events during lb-push; Sailor returns actual first acceptance/correction and execution facts. `lb-update` records reconciled outcomes and performs Stage/logbook close-out. Use the adapter to resolve the unique Thinking, then supply its path explicitly; the CLI never guesses binding by filename and cannot authenticate that caller-supplied adapter result.

- `lb log context THINKING --json` gives the document/state pair's token; structural check of a Thinking is not required.
- `lb log events record LOG --thinking PATH --input-file FILE --expect-version TOKEN --dry-run --json` appends a validated event. Repeat without dry-run only after reviewing the diff. Unclosed fences/comments refuse append without mutation; the final candidate must expose the recorded event. Inputs stay inside the approved root; scratch files are not deliverables.
- `lb log report --view metrics LOG --thinking PATH --run-id ID --scope logbook|EXACT_STAGE --json` computes the shared event model. The old run-metrics.py entry delegates to this same calculation.
- `lb log report --view closeout LOG --thinking PATH --run-id ID --scope logbook|EXACT_STAGE --json` returns state, checklist counts/open responsibility, link inventory and statistics. Missing Thinking/events gives explicit unknown coverage.

Thinking’s `lb/` state section retains run-event records; never add JSON fences to its body. Same run/event IDs are idempotent; conflicts fail. Wait/interruption intervals use unions, not duration sums. A recovery or skill switch does not reset run/package identity. Later defects correct an erroneous first-pass pass. Unknown interactions, partial timing and absent denominators remain unknown. Remaining wall time is not net execution time. The report does not run cleanup, complete human tasks, accept deliverables or create new obligations.

At Stage/project close, update reports elapsed/wait/interruption coverage, human interaction count and first-pass numerator/denominator with scope. Unknown metrics are not an extra Stage gate. Keep the compact summary in Thinking, not a growing block at the top of the Logbook.

## Workflow CLI

`lb-workflow` owns semantics and authorized template maintenance; `lb-scaffold` owns creation and adapter bindings. Commands: workflow list/show/check/create/update/render/set-status/diff; log create. Skills own semantic decisions and orchestration; each CLI mutation owns one file only. Run check before rendering. Check reports a structural-marker subset and its coverage; it does not certify semantics or real use. For an authorized template revision, prepare a complete candidate inside the approved root, then use `workflow update NAME --content-file FILE --expect-version TOKEN --dry-run`; inspect the diff, write and reread. Replace uses CAS and touches neither companions nor instances. For a new template, the skill prepares its approved docs directory and reviewed candidate; `workflow create NAME --content-file FILE --dry-run` previews one canonical file, then creates it without overwrite. It does not create directories or companions. For workflow render or log create supply `--expect-version` from workflow show plus `--input-file FILE` containing exactly:

```json
{"date":"2026-01-01","working_directories":"- local\n  - `/approved/example`","rulings":{"SUBJECT":"Example"}}
```

Rulings map exact placeholder names (without brackets) to values. Date and directories are the other two slots. Render preserves declared fenced YAML front matter; supply its placeholders, including prev-run where present, through rulings. It replaces only a standalone `<WORKDIRS>` or a contiguous directory list, preserving following prose/rulings. Ambiguous directory layouts are refused for explicit template maintenance. Substitution is one pass. Render refuses remaining placeholders or legacy ambiguous template layout. Log create checks deterministic candidate errors at the actual output path and publishes a create-only document and its `lb/` state under an existing approved parent: `log create PATH --from-workflow NAME --input-file FILE --expect-version TOKEN --dry-run`, then write. It reports bindings pending and never claims managed setup complete; scaffold must create/check the uniquely bound Prompt/Thinking and index via the existing adapter. Retry inspects a partial file before choosing recovery, never overwrites it.

Provenance pins the template digest and inputs. Diff reports template drift and never updates an existing route. Catalog and structural checks are derived views, not another editable template store. Contract-valid does not mean real-instance-validated. Installer name conflicts preserve host copies instead of replacing them.

## Main-branch retrospective

During execution, Sailor supplies actual skill usage and lessons; project Captain saves significant facts immediately. At close-out update leaves concise feedback and source references. Invoke lb-retro on the host main branch for cross-logbook synthesis; it is not a compulsory task in each project and installs no scheduler.

`lb feedback scan --since YYYY-MM-DD --ref master --ledger PATH --json` reads a fixed committed snapshot and reports uncommitted exclusions. An existing ledger is optional for scanning. It returns candidate source occurrences, not AI-assigned defects. Other branches/worktrees and their unmerged returns are not inspected; an empty scan is not proof that no such feedback exists. Historical backfill stays distinguishable from this period's actual incidents. Explicitly classify original sources before proposing a fix.

`lb feedback show --ledger PATH [--id ID]` reads existing findings and its token. `feedback record/update --ledger PATH --input-file FILE --expect-version TOKEN --dry-run` writes accepted maintenance on the master checkout, preserving old prose. It refuses writes on another branch instead of switching. Records carry stable IDs and three separate dimensions: disposition, implementation/verification, actual adoption references. A verified implementation needs evidence; planned usage does not count as adoption. Closed findings remain. Source IDs are durably recorded before suppression on the next scan; there is no time-only checkpoint that can skip unsaved findings. User approval/scope gates still govern implementing proposed changes or adding tasks.

## Same-machine runtime identity

New packages prefer the Captain's machine unless an already authorized remote requirement justifies another. This changes neither model/deployment constraints nor directories. Existing remote work is not migrated or stopped automatically. Raise core direction/permission/capability questions early with facts, impact and a recommendation; continue routine technical judgment within authorization.

Use `agent bind` for dispatch-bound full handles and `agent inspect --live` for
runtime observations under the [domain contract](domain-commands.md). Saved bindings
are not live proof. `agent send/close` require a matching live session and observation;
missing runtime session identity refuses control. There is no separate runtime record
model, caller-supplied observation checker or alias command family.

## Atomic operations and skill orchestration

Do not replace lb-workflow or lb-scaffold with a workflow executor CLI. The skill authorizes and reviews semantic changes, chooses inputs/output, orders commands, verifies companions and handles partial completion. Each write command reports only its file effect. Closeout aggregates recorded evidence, not live session cleanup; lb-update aligns returns and the authorized execution flow checks/releases actual Herdr resources. No new session inventory or cross-branch scheduler is introduced.

Machine records and recovery follow [document state](document-state.md). Skills
notify users when lb fails and continue safe authorized work under its fallback;
missing tooling never turns an unrecorded outcome into accepted state.
