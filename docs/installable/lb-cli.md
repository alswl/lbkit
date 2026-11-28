# `lb`: the guarded lightweight Logbook CLI

## Markdown SSOT and new-run commands

For new runs, the [document state contract](document-state.md) defines storage and
sync. Initialize with `log init-state LOG --name NAME [--document PATH ...]`, then
identify Tasks and explicitly run `log sync-state LOG`. Queries read current
Markdown and return sync_status. Document edits return sync_required and require
no caller document token. Task replacement also updates the dependency graph.
`log sync` retains its separate
stage/summary editing purpose. Use `--dry-run --json` to inspect authorized writes.

Task execution interfaces:

- `task assign|unassign LOG TASK --input-file FILE --expect-execution-version TOKEN`
- `task bind-execution LOG TASK --input-file FILE --expect-execution-version TOKEN`
- `task agent inspect LOG TASK --binding-id ID`
- `task agent send LOG TASK --binding-id ID --operation-id ID --expect-execution-version TOKEN --expected-session ID --expected-observation VALUE --message-file FILE`
- `task result-source LOG TASK --input-file FILE --expect-execution-version TOKEN`

Use `log route LOG --json` to read the reviewable graph and `route_ref`. Run
`task depends LOG --task-id ID --input-file FILE --expect-route ROUTE_REF` to
replace one Task's dependency list. The file contains `{"depends_on": ["ID"]}`.
An empty list clears the Task's dependencies. The response includes the new
route reference and changed Task scopes. Preview the edit with `--dry-run`.
Dependencies move to `lb/<name>.dependencies.json` on the first eligible Run
write, preserving prior route confirmations when the graph is unchanged. See the
[dependency authority and rollout contract](document-state.md#task-dependencies).

Execution tokens come from `log execution context LOG --json`. Assignment payload
is `{subject:{kind,subject_id},basis}`; unassign uses `{basis}`. Binding requires
id, assignment_revision, machine, session_id, adapter=herdr, runtime_locator
(workspace_id, tab_id, pane_id, agent_id, server), work_context (repository_ref or
null, working_directory, and optional cli_launcher), input_ref, basis and
observed_at. Bindings are immutable. Replaying the current Binding is idempotent.
Replacing it requires a new Binding ID.
For Herdr bindings, `machine` selects the transport host (`local` or a configured
machine profile); `server` is the selected server session scope, not the machine
name. For `local`, inspect `herdr status --json` and require a running compatible
server; use its nonempty `session` exactly, or the lb scope `default` when Local
reports no named session. For a remote machine, inspect the enabled saved profile
locally, require its explicit `session` to match `server`, and use its stable ID for
subsequent API calls. Never forward Local-only status remotely, substitute `local`,
guess a default remote session or fall back to Local. Do not retarget an unrelated
server to make a binding match. Use this same observed scope in execution
runtime_locator and monitoring binding; workspace/tab/pane and native session
identity must come from that server.

Result source payload is `{ref,source,version_ref?,observed_at}`, with source either
`{binding_id}` belonging to this Task or `{kind,subject_id,basis}`.

These runtime writes require synced current Task content. Send also retains live
identity, active lifecycle, dependency, human and takeover protection. Send intent
is durable before transport; unknown forbids resend. Existing execution record
reconciliation remains available after Task deletion or stale Markdown.

`agent monitoring context LOG` and `agent monitoring configure LOG --input-file FILE
--expect-version TOKEN` replace the independently stored Observation setup for new
runs. Configure accepts `{targets:[]}`; managed wait returns no_targets without
runtime calls, retaining pending events/answers. Raw wait still requires 1..64.
Event and Answer commands retain their own contracts and monitoring tokens.

New Task flows do not use Dispatch/Attempt or record-result/accept. Legacy domain
writers are refused in the new document mode, rather than silently storing a second
Task state. Configuration and template tokens are unchanged. The historical command
reference below describes older layouts where specifically named; it does not
restore old sidecar/CAS obligations for new document runs.

### Legacy run migration

```sh
lb log migrate-state docs/delivery.md --name delivery --dry-run --json
lb log migrate-state docs/delivery.md --name delivery --apply --expect-plan PLAN_TOKEN --json
lb log migrate-state docs/delivery.md --name delivery --rollback --dry-run --json
lb log migrate-state docs/delivery.md --name delivery --rollback --apply --expect-plan ROLLBACK_TOKEN --json
```

Use the same `LOG`, `--name` and repeated `--document PATH` options for preview
and apply. A bound legacy execution record supplies its Thinking path. Preview
reports source ownership, destination, checksums, identities, old sends, and
unresolved Events and Answers. A plan token is issued only for an applicable
preview. Neither preview, apply nor rollback contacts a runtime or sends a
message. Stop older clients and quiesce the affected runtime workflows before
cutover or rollback. Current clients also refuse cooperating writer and listener
lock conflicts.

A supported run has a valid, unique Logbook UUID, document policy represented
equivalently in Markdown, and an unused unified destination. The command refuses
unselected sections in a shared sidecar, unsupported document records or
unverified Dispatch attempts, unresolved ownership, old release or handoff facts, legacy
write journals and saved active listeners. Observation ownership comes from the
Logbook's sidecar UUID. Path-keyed or separate associated-document monitoring
stores require reconciliation before migration.

Migration retains legacy link verifications and Task archives under
`legacy_history` in `log context`. Historical link observations preserve their
original scope and never count as current verification or authorization. Older
unified files may also retain history under `documents[path].legacy_metadata`.
Context exposes that section as `legacy_metadata` alongside any `legacy_history`.
Archived Task IDs remain reserved throughout the run. Migration refuses an archived ID
also used by current work, an ambiguous replacement path, or a second Markdown
archive for the same ID. Legacy Task basis, history and source disposition are
retained under `legacy_history.task` by stable Task ID. They confer no current
effect or permission. Markdown determines current Task state and dependencies.
A saved legacy disposition must match the readable Markdown Resolution and
current Task text. Missing, stale or conflicting dispositions refuse migration.

Run events and skill returns from the bound legacy Thinking are historical
evidence. They establish no current skill effect, authorization or runtime
binding. Migration retains a finished, failed or interrupted Attempt only
with a complete Dispatch closeout, consistent timestamps, and one matched
submitted delivery. That Attempt keeps the duplicate-start guard in effect.
A still-open Dispatch with an Attempt, a started Attempt, or contradictions
between closeout and delivery require reconciliation before migration.

Old sends require an independently attributable Dispatch, stable Task ID,
recipient and saved binding matching the recorded package and binding digests.
A verified closed Dispatch may retain an archived Task ID. Its history stays
with that ID and is never reassigned to a replacement Task.
A Dispatch cancelled directly from prepared with no Attempt or send operation
keeps its cancellation and any verified binding as history only.
Migration keeps the original requests, outcomes, receipt provenance and
Dispatch-to-Task association. An unknown delivery blocks further dispatch and
retains evidence-based reconciliation by operation ID. Submitted delivery blocks
another start for the mapped Task until attributed business-action evidence is
recorded. Evidence that the task already started keeps the legacy start guard in
effect. Migration records no new assignment, binding or authorization. Read
fresh execution and monitoring contexts after cutover.

Apply rechecks the reviewed plan under writer exclusion. It writes a private
`lb/<name>.migration-backup` with original bytes and their checksums, then
publishes the unified state and its durable authority receipt. Legacy files remain
in place. Current clients fence both paths if publication stops before the
receipt or if a published destination disappears. Repeating the same applied
plan returns its original receipt. After exit 3, inspect the authority and retry
the same reviewed command. Verified prepared state can finish an interrupted
publication without repeating runtime effects.

Rollback requires its own preview token. It verifies the original sources and
requires unchanged Markdown and unchanged unified state since cutover. It
atomically replaces the unified state with a rollback receipt and resumes legacy
authority from the original files. Repeating rollback returns its receipt. A
retired apply token cannot republish the old plan. Changes after cutover require
explicit reconciliation rather than automatic rollback.

Usage errors exit 2. Persistence or access failure during apply or rollback exits
3. An unsupported, unsafe, conflicting or stale plan exits 4. Existing
`log recover` handles interrupted legacy document transactions while legacy
authority is active.


`bin/lb` uses Python 3.11+ and Click, with a uv-locked environment, built for structured reading of this repo's Markdown conventions and minimal-scope edits. Skills own scheduling, authorization and evidence judgment. The CLI records atomic transitions and reports; explicit agent transport commands can contact the configured runtime after identity checks. A recorded acceptance is an attributed decision, not a CLI business verdict.

```sh
# Discover conservatively recognized main logbooks (default scan: projects/*/docs/*.md)
bin/lb log list --json
bin/lb log list --projects-dir records --json  # maps to the host's settings.documents.project_root

# Read stages, next item, working directories, links, and the concurrency version token
bin/lb log context projects/example/docs/logbook.md --json

# Check one logbook, or check all discovered logbooks
bin/lb log check projects/example/docs/logbook.md
bin/lb log check --all --json

# Structured state snapshot (derived summary, stage counts, 🔮 gate, top status-line ownership)
bin/lb log state projects/example/docs/logbook.md --json

# Sync delivery-stage H2 emoji and the adopted top status line; inspect a dry run first
bin/lb log sync projects/example/docs/logbook.md --expect-version 0123... --dry-run

# Pass the version_token returned by context unchanged into precise write operations
bin/lb task update projects/example/docs/logbook.md \
  --stage 'Stage 01 Implementation' --task 'Development: Implement the CLI. @logbooks 🤖️' \
  --status / --expect-version 0123... --dry-run
bin/lb task artifact projects/example/docs/logbook.md \
  --stage 'Stage 01 Implementation' --task 'Development: Implement the CLI. @logbooks 🤖️' \
  --artifact '产物：[CLI](../bin/lb)' --expect-version 0123...

# Append a todo to a confirmed stage, or place it before an existing todo in that stage
bin/lb task add projects/example/docs/logbook.md \
  --stage 'Stage 01 Implementation' --text 'Test: Verify the CLI. @logbooks' --expect-version 0123... --dry-run
bin/lb task add projects/example/docs/logbook.md \
  --stage 'Stage 01 Implementation' --text 'Test: Verify the CLI. @logbooks' --before-line 42 --expect-version 0123...

# Append one short fact under an agent todo; kind is one of 产物, 阻塞, 状态, 交接
bin/lb task note projects/example/docs/logbook.md \
  --stage 'Stage 01 Implementation' --task 'Development: Implement the CLI. @logbooks 🤖️' \
  --kind 阻塞 --text '🚨 The human owner must sign in; resume after login.' --expect-version 0123... --dry-run

# Append one Markdown link to a stage's 相关链接： block (created before 待办： when absent)
bin/lb log links add projects/example/docs/logbook.md \
  --stage 'Stage 01 Implementation' --link '[PR #12](https://forgejo.example.com/o/r/pulls/12)' --expect-version 0123... --dry-run

# Rewrite link targets by prefix, e.g. after merging a worktree; every rewritten target must exist
bin/lb log links rewrite projects/example/docs/logbook.md \
  --from 'file:///Users/me/ws/app/.worktrees/feat-x/' --to 'file:///Users/me/ws/app/' --expect-version 0123... --dry-run

# Human todos only, or just the next item
bin/lb task list projects/example/docs/logbook.md --human --json
bin/lb task list --status in-progress --json
bin/lb task next projects/example/docs/logbook.md --json

# Approved work-type recipes in lbkit-skills.yaml; settings and agents use lb config and lb config agent.
bin/lb config recipe list --status available --json
bin/lb config recipe show documentation --json
bin/lb config recipe create documentation --input-file recipe.yaml --expect-version TOKEN --dry-run
bin/lb skill history --since 2026-10-01   # skills actually invoked in Claude Code and Codex sessions; the only command reading outside --root (~/.claude, ~/.codex), counting only sessions whose working directory falls in a logbook-registered directory or this repo
bin/lb skill extract --json   # 「技能：」 sub-lines not covered by any entry (skill chain or companion skill), listed verbatim with the todo's original text, completion status, and the work package pointing back to it
```

`--root` defaults to the current directory. Resolve explicit `LOG`,
`--document`, `--thinking` and `--input-file` paths relative to that root.
Absolute arguments must resolve inside it. A companion document must belong
to the Logbook's project and, when used for an existing run, be bound to
that run. The project root is the closest ancestor of the Logbook with
`mind.yaml` within the invocation root, with the invocation root as the
fallback. Saved document keys are relative to that project root.

```sh
bin/lb --root . log context projects/demo/docs/log.md --json
bin/lb --root projects/demo log context docs/log.md --json
```

With `projects/demo/mind.yaml`, both calls select the same Logbook and run.
Markdown links remain relative to the document. A runtime binding's
`working_directory` remains an absolute path on the bound machine.

`log check`'s `DUPLICATE_TASK_TEXT` flags unclosed same-text tasks within one Stage (historical duplicates that are all checked no longer warn) — a preview that later write commands targeting the task's original text will be rejected as ambiguous. `local_target` runs expanduser ownership judgment on links starting with `~`; those outside the root still count as LOCAL_LINK_UNVERIFIED.

The "next item" in `log context`, `log state`, and `todo` is computed only from unfinished (`[ ]` or `[/]`) todos in `Stage NN` delivery stages (`NN` may carry one letter suffix, e.g. `Stage 03b`); global checkbox lists in an old logbook's Overview take no part in scheduling.
`task list` and `task next` use the same delivery-stage scope; `task list` filters by stage, status, and human ownership, and lists todos across all discovered logbooks when the logbook path is omitted.

Discovery defaults to `projects/*/docs/*.md` inside the root; `list`, `log check --all`, and `task list` accept `--projects-dir` to pass in the host-configured `settings.documents.project_root`, and recognize candidates with the heuristic "exactly one visible H1, plus an H2 stage or a todo"; this excludes `thinking/` and `prompts/` but is not a semantic classifier for arbitrary articles. The `projects`, project, and `docs` directories all get containment checks before traversal; directories pointing outside the root or otherwise anomalous are not traversed. Headings, todos, and links inside code fences and HTML comments do not participate in parsing; a trailing HTML comment hides only the comment itself, so a task before the comment keeps its full original text and updatable identity. If a multiline comment's closing line is followed by structural text, `COMMENT_STRUCTURE_AMBIGUOUS` is reported rather than guessing the parse. A fence closes only with a fence of the same character, sufficient length, and nothing but whitespace at end of line. `context.stages[].tasks` gives each item's original text, status, line number, repository marker, and human marker. `bound_records` lists only places in the body that explicitly link to `thinking/` or `prompts/` — bindings are never guessed from same-named files.

## Herdr resource creation

```sh
lb --root ROOT herdr -- tab create --workspace w1 --cwd /example/repo --label reviewer --no-focus
lb --root ROOT herdr -- pane split w1:p9 --cwd /example/repo --no-focus
```

The proxy consumes `settings.runtime.herdr.label_prefix` from the host's
`lbkit.yaml`. It prefixes display names, never logical Agent IDs, and reads back
the exact newly returned resource ID. It does not select a runtime/model, replace
an approved wrapper, grant dispatch permission or implement guarded business send.
Reuse and tab preference remain Skill decisions. Focus flags are preserved;
Skills supply `--no-focus`. Workspace creation is outside managed naming support.

All tokens after `--` belong to Herdr, including `--json` and `--dry-run`. Empty
argv is a usage error (2), never a launch of the native TUI. There is no shell
evaluation or extra proxy timeout. Unknown command paths and native help/version
pass through once with inherited stdio and native exit status. Recognized creation
with unsafe/unsupported arguments also passes the original argv once, adding
`configuration_not_applied` to stderr; it reads no policy and performs no rename
or readback. This is the B pass-through policy, not proof of configured naming.

Supported creation syntax (based on Herdr 0.9.5):

| Path | Options |
| --- | --- |
| `tab create` | `--workspace`, `--cwd`, `--label`, repeatable `--env`; `--focus` or `--no-focus` |
| `pane split` | One positional pane, `--pane`, or `--current`; `--direction`, `--ratio`, `--cwd`, repeatable `--env`, `--right-click`; `--focus` or `--no-focus` |

The classifier recognizes separate and equals forms without shell parsing; native
syntax validation still belongs to Herdr. Herdr 0.9.5 creation accepts the separate
forms shown above and rejects equals options such as `--label=value`; that native
failure is preserved, not converted into a successful creation. Global `--machine`
and `--session` selector tokens are retained unchanged on derived commands. Unknown leading
syntax is forwarded without guessing a command position. Duplicate scalar options,
missing values, conflicting focus/targets and unknown creation options take the B
path; option values containing command words remain data.

For safely parsed creation, configuration is read before allocation. Missing or
invalid configuration refuses with exit 4 and no allocation. An absent/empty prefix
forwards unchanged, without extra naming/readback. With a nonempty prefix, an
explicit tab label is prefixed before creation, then verified. Otherwise the new
tab's native label supplies the base name; a pane uses its first nonempty label,
title, then terminal_title_stripped, falling back explicitly to its returned pane
ID. Only that resource may be renamed and read back. A complete existing prefix
is not doubled; text is not trimmed.

Native creation failure preserves original stdout/stderr bytes and exit status,
with no naming follow-up. Successful creation preserves its stdout. Missing ID,
rename failure, read failure or label mismatch adds a stderr JSON diagnostic with
`reason`, `stage`, `resource_kind`, `resource_id` (null when unknown), known
`owned_panes` and `retry_safe: false`, then exits 4. Inspect and repair the known
resource; the proxy never retries allocation, deletes resources, guesses the last
resource or renames unrelated resources. Signals use shell status 128+signal;
missing/nonexecutable native binaries return 127/126. Interrupted transport may
have side effects and must be reconciled before retrying.

`lb agent herdr open --input-file FILE --json` is a Herdr-specific lifecycle
operation. Its six inputs (machine, server, parent_pane, cwd, runtime, name),
no-focus pane layout and native runtime restriction belong to that backend, not
to a general Sailor contract. The logical agent name remains unprefixed.
It shares the naming service and verifies prefix+name before starting the runtime.
Success adds `display_policy` (`verified` or `not_required`) to existing fields.
Naming failure returns exit 1, `status: unknown`, the known `owned_panes`,
`failure_stage` and failed `display_policy`; no runtime is started. Other lifecycle
failures retain the documented failure contract. `lb agent herdr close-session`
accepts the returned binding and owned_panes, checks native identity and closes
only its explicitly owned pane.

Remote lifecycle opening verifies the parent pane through the selected profile
before creating a pane. Missing, ambiguous, disabled or mismatched profiles refuse
without Local fallback.

The generic `agent open` and `agent close-session` routes are removed without
aliases. Use the explicit Herdr routes and valid host configuration before
allocation. Sailor delegation selects a collaboration adapter; it does not define
tab/pane topology or display-name policy. `config check/resolve` never certify runtime adoption.

## Write and Concurrency Protection

Every write operation (including `log sync`) must supply the SHA-256 `version_token` returned by `log context --json` or the preceding successful write. Any single-byte file change, or a stage and task original text that cannot be uniquely matched, refuses the write with exit code 4; an invalid status value is a parameter error with exit code 2. Tasks are located by the stage heading (minus the status emoji) plus the full original task text — never by line number. `task update` and semantic task state commands allow human-owned state changes with `--confirmed` after explicit human confirmation; without it only pending-to-active is allowed. Confirmation does not bypass CAS, dependencies, valid transitions, migration or preflight checks; `task artifact` and `task note` require `--confirmed` for explicitly human-approved details on human-owned items, except `task note --kind 状态` (`Status`), which appends a status sub-line and leaves the first line and checkbox untouched. `task add` creates only not-started items and rejects same-text todos in the same stage; `--before-task` matches exact task text uniquely in that stage; it is mutually exclusive with legacy `--before-line`, which must point to a task first line. Line numbers shift after every insert, so repeated `--before-line N` with the same N places each later item before the earlier one; use `--before-task` with the same anchor text to keep insertion order. Before using `task add`, an agent still needs the human's explicit confirmation of the new items and their order. `--dry-run` writes nothing and prints a reviewable unified diff (the JSON `diff` field).

All write commands re-parse the candidate text before writing and reject newly introduced deterministic `log check` issues (such as missing in-repo links). Pre-existing issues do not block unrelated local updates; transient stage emoji, explicit `[-]`, unfetched external links, and unverified local links outside the repository count as permitted notices. The `issues_introduced` field of the JSON write result is an empty list when admission passes. `task artifact` and `task note` place new sub-lines after the existing indented sub-items; appending a duplicate is refused when an identical sub-line already exists. `task artifact` prepends the `产物：` (`Artifact:`) label when the text does not already start with it. When `task note` text starts with `🚨 ` and a `--kind` is given, the marker stays at the very front of the sub-item body.

Before writing, the tool re-checks root containment and the source file's bytes after fsyncing the temp file and before `os.replace`, then performs the same-directory atomic replacement. This narrows the clobber window of ordinary concurrent editing but is not a CAS/lock guarantee against arbitrary editors or malicious processes; on conflict, still re-read context after the refused write.

Paths resolve symlinks on both read and write, and targets must still lie inside `--root`. The exception is read-only `skills usage`: it reads session records from `~/.claude/projects` and `~/.codex/sessions`, reporting only sessions whose working directory falls in a logbook-registered directory or this repo. Edits preserve UTF-8, the original CRLF/LF style, and all untouched bytes; `log sync` only changes the H2 emoji of delivery stages whose status is determinable — empty stages, unresolved `[-]`, and unknown statuses are never silently judged complete. An unresolved `[-]` is reported by `log check` as a skipped record, neither an approval signal nor a blocker: `next_task` skips it and advancement continues with the next unfinished item; a valid task disposition permits closure without claiming acceptance.

## Checks, Status, and Limits

Each `log check` diagnostic includes `path`, `line`, `code`, `message`, `category`
and `severity` in JSON. Text output also shows the category and severity. Exit 1
means at least one `error` and exit 0 allows any number of `notice` diagnostics.
Exit 2 is a command parameter error, 3 is path/read refusal, and 4 is concurrency
or write-protection refusal.

| Category | Severity | Examples |
| --- | --- | --- |
| `structural_error` | `error` | `EMPTY_STAGE`, `INVALID_STAGE_PLACEHOLDER`, `UNKNOWN_TASK_STATE` |
| `status` | `error` | `STAGE_EMOJI`, `SKIPPED_EXPLICIT`, `PREFLIGHT_BLOCKER` |
| `broken_link` | `error` | `LOCAL_LINK_MISSING` for an in-root path confirmed missing |
| `verification_limit` | `notice` | `LINK_UNVERIFIED` for external links without an applicable verified observation, `LOCAL_LINK_UNVERIFIED` for out-of-root or unreadable paths |
| `stage_placeholder` | `notice` | `STAGE_PLACEHOLDER` for a [declared empty delivery Stage](logbook-format.md#status-and-links) |

Checks run offline. Local link checks cover path existence within the root.
External and out-of-root link notices leave availability unknown. Keep run
identity links in the Logbook even when they have no applicable verification.

## The 🔮 preflight gate

When any todo's or indented sub-item's checkbox text contains `🔮` (a pending-discussion blocker produced by lb-preflight and written in after human confirmation), the whole logbook is considered halted:

- `log context --json` returns `preflight_blockers` (each with `line`, `text`, `indent`, `stage`) and `preflight_clear: false`; each task's `preflight` boolean marks whether that line is a blocker.
- `log check` reports `PREFLIGHT_BLOCKER` for every 🔮 checkbox line (a deterministic status record, same class as `[-]`'s `SKIPPED_EXPLICIT`, contributing to exit code 1).
- `log sync`, `task update`, `task artifact`, `task add`, `task note`, `task rewrite`, `task split`, `task resolve`, `link add`, and `link rewrite` all refuse to write with exit code 4, with the error naming the line; the CLI offers no bypass flag — the only way out is a human rewriting or removing the 🔮 in the logbook text, then re-fetching `log context`.

The tool only detects markers and does not verify a 🔮's provenance; write and adjudication semantics are in [Logbook Format](logbook-format.md) and the lb-preflight SKILL.

## Top Status Line and Structured State

Manage status emoji through this script first; do not hand-edit H2 emoji or the machine-readable status segment. `log state --json` gives a structured snapshot: overall counts (delivery stages done/in_flight/not_started), `summary` (the derived machine-readable string), `next_task`, the 🔮 gate, and the `owned` attribution of every `> 状态：` line.

The CLI creates a missing compact status line; lifecycle-managed pages use the one-line renderer described in [lifecycle operations](lifecycle-operations.md). Legacy human commentary and free-text status remain protected; explicit migration is required before lifecycle takeover. Existing un-migrated owned legacy lines retain their former rendering for compatibility. `log state` reports lifecycle, generated_status, actionable and inconsistency fields. `log state-set` records lifecycle plus the generated line atomically using the current token. Normal writes stop while paused/completed/terminated. Only lifecycle pause/termination may preserve an unresolved 🔮 while recording that terminal control decision; it cannot clear the gate or advance tasks.

For managed active logs, the generated status selects the first delivery Stage
in route order with an active or blocked task. If that Stage only has blocked
work, the status shows the blocked marker. With no such Stage it falls back to
the candidate. The whole-log 🔮 gate retains display priority. `next_task` still
reports the scheduling candidate and can point to a later Stage. Execution
continues to enforce dependencies and the other admission gates.

Running tests:

```sh
uv run --locked python -m unittest discover -s tests -v
```

## Removed companion view

`lb todo` is no longer supported. Use `task list`, `task next`, `log context` or `log state`; human-readable summaries belong in the response. Protected writes never create or refresh TODO.md or a replacement view. Existing consumer files are preserved.

## Skill Integration and Evaluation

lb-* entries call the CLI at their respective steps; the shared flow is in [document adapters](../../skills/lb-update/references/document-adapters.md#cli-invocation-in-this-repository): plan reads and checks, push marks in progress after taking a task, status queries and syncs authorized emoji, update updates status and artifacts after evidence acceptance; preflight is a read-only analysis entry, with blocker write-back done by the skill within the logbook write boundaries — never through CLI write subcommands. The script neither runs these skills itself nor checks task authorization or evidence sufficiency.

The external verification suite runs multi-step CLI flows on synthetic logbooks, verifying token refresh, concurrent-edit protection, artifact handoff, and read-only queries; each skill's `evals/evals.json` separately holds model decision scenarios. Passing CLI integration tests is not the same as passing model behavior evals; the latter also requires actually running the skills in a controlled environment and inspecting tool calls, file diffs, and answers — verbal plans alone are not scored.

The implementation lives in `src/logbook_cli/`: `commands/` handles Click parameters, `services/` handles use cases, `storage.py` guards writes, and `render.py` handles output. `models.py` defines semantic states and task annotations; `format.py` maps Markdown labels and markers. `document.py` parses and checks; `views.py` derives status and task-query views; `edit.py` performs minimal text edits. `bin/lb` use the existing checkout environment. For module execution use `uv run --locked python -m logbook_cli`. Install or refresh dependencies explicitly with `uv sync --locked --no-dev --project .lbkit`; reads never install or access the network.

Reproducible fixture preparation, non-clobbering prechecks, and event collection are described in the consuming repository's behavior-eval process.

## Document metadata

Follow [document state](document-state.md) for the `lb/` state layout, task identity,
rename/move/delete/merge rules, paired-file CAS, recovery and skill fallback.
Machine JSON is not stored in Markdown. Old inline records are unsupported;
there is no migration workflow. The only active reserved comment is a short task ID.

## Feedback-era Write Extensions (0.2)

Successful logbook writes return `version_token` for the resulting Markdown and its state section, including no-op writes. Dry-run returns the original current token, not a token for the uncommitted preview. This removes token-only reads between already-understood sequential writes; it does not make the sequence transactional or replace semantic rereading after conflicts or changed acceptance criteria.

`task rewrite LOG --stage STAGE --task OLD --text NEW --decision SOURCE --expect-version TOKEN` changes only an unfinished task's first-line text, preserving its checkbox, position, children and repository ownership, and records the supplied decision in a status child. Human items require `--confirmed` after approval of that exact rewrite. Completed/skipped items, changed ownership, duplicate text and stale tokens remain refused. The caller must verify authorization and evidence applicability; the CLI cannot authenticate the supplied decision.

For an explicitly authorized initial assignment, add `--assign-repo NAME` (without `@`) and include exactly `@NAME` in the new text. This permits assigning one repository only when the original unfinished agent task has none; it never transfers existing ownership or splits the task. Preview first with the same decision and token. The caller verifies the named repository is in the approved working directories and that the human decision authorizes this assignment; the flag and decision string cannot authenticate consent. All other rewrite protections remain in force.

`task split LOG --stage STAGE --task ORIGINAL --into FIRST --into SECOND --decision SOURCE --expect-version TOKEN` replaces one unfinished agent package with at least two new, ordered, not-started tasks in the same stage, in one guarded write. Preview the entire transformation with `--dry-run`, inspect it, then write with that same token. The original task is removed from the current list and its complete content is retained in the sidecar `task-archive`. Replacements remain unfinished and inherit no accepted state or artifact. This changes the earlier split behavior that retained a skipped parent. For identified tasks, use `--input-file` with `task_id`, replacement `{id,text}` entries, and `reference_changes` mapping each dependent task to its new dependency IDs. Missing maps, cycles and unresolved live bindings refuse the whole operation.

Duplicate or existing replacement text, human/completed/skipped originals, human replacements and preflight gates are refused. If the original has repositories, replacements must collectively cover exactly those repositories and each must retain at least one; new repositories and loss of an existing repository are refused. An unassigned original may give each replacement at most one explicitly named repository. The caller verifies the human-approved scope, order, repositories and evidence applicability; `--decision` cannot authenticate consent. All candidate validation and CAS checks finish before any byte is written. Failed validation or stale tokens leave the original and replacements unchanged. Repeating a completed split is refused. Stage marker synchronization remains a separate current-token operation, as with `task add`.

`task resolve LOG --stage STAGE --task TEXT --as human-cancelled|not-applicable --decision SOURCE --note REASON --expect-version TOKEN` adds a task-bound disposition to an already `[-]` item, including a human-owned item. It never changes the checkbox. The visible `处置：` child contains readable disposition, decision and reason. The existing `lb/<name>.md.json` task record holds `task` (SHA-256 of exact task text), `as`, `decision`, and `note`; an unidentified item gains a short ID in the same transaction. Missing, conflicting, malformed or stale records do not close the task (`INVALID_RESOLUTION`). A changed task text invalidates the record; a mere `--as` option does not prove a human decision occurred.

Stages whose items are all accepted or explicitly dispositioned derive ✅. Context exposes each task's resolution; task queries retain the distinction between unresolved skips and dispositioned items. Summaries say “已收口（含取消/不适用项）” rather than claiming successful acceptance. All-skipped stages can close only with valid dispositions for every item. Existing unresolved skips retain their old non-pass behavior.

`link add LOG --stage STAGE --link '[label](target)' --expect-version TOKEN` appends one Markdown link as a list item to the stage's `相关链接：` (`Related links:`) block, creating the block right before `待办：` when the stage has none; an identical existing line is refused. `link rewrite LOG --from PREFIX --to PREFIX --expect-version TOKEN` replaces the prefix in every visible link target (code fences and comments untouched) and returns the `rewritten` list; it refuses the whole write when any rewritten target does not exist (`file://`, `~` and relative targets are resolved for this). That existence check covers only the links it rewrites: `log check` still reports links outside the root as `LOCAL_LINK_UNVERIFIED` without probing them.

The low-level CLI remains a standard-library Markdown tool for inspection, migration and testing. Managed lb-* document workflows require mind-forge; CLI success does not establish mind-forge readiness, authorization or acceptance.

## Protected task details and offline observations

`task note --kind` also accepts Source/来源, Acceptance/验收 and Skills/技能. Values are single nonempty lines; new Skills are four-space-indented slash/backtick spans. Historical chain forms remain readable. Without `--replace-line N`, notes append and all Acceptance entries remain conjunctive. With that option, explicit Source/Acceptance/Skills/Status replaces exactly the matching current task annotation line; a mismatch, stale token or ambiguous task is refused. Status replacement maintains a current fact such as the Captain takeover marker without changing the task checkbox or first line. Without confirmation, human items accept only the additive Status exception. With explicit human approval and `--confirmed`, note/artifact may append details and note may replace the exact same-kind annotation line. Source/Acceptance append or replacement on `[x]` or `[-]` tasks requires an authorized reopening first; Skills correction establishes no new acceptance. Context exposes annotation kind/value/line and parsed skill names/diagnostics. Changed conditions invalidate affected returns/bindings.

Machine groups accept `- ` followed by a backticked explicit machine name, alongside legacy local/remote groups. Context preserves machine spelling and adds machine_name/group_kind. `skills usage --machine NAME` includes only that named group plus legacy local groups and this repository; without it named groups are not scanned. This selector grants no remote access and probes no remote filesystem.

```sh
bin/lb log links record-check log.md --line 18 --target 'https://sources.example.com/reference/12' --label 'Primary reference' --observed-at '2026-10-14T08:00:00+08:00' --observer sailor-a --basis 'Read with the host tool' --outcome verified --expect-version TOKEN --dry-run --json
```

`log links record-check` registers an offline observation of one visible link
selected by current line, target and label. Overview, Source, Stage and protected
human links are eligible alongside Artifact links. For a link outside a Task,
use `--bind-stage` and `--bind-task` together to supply its binding. A link inside
a Task binds to its owning Task. `--result-identity` records a supplied revision.
Use `--outcome verified|unavailable|revoked`. Sailor performs the observation,
Captain aligns the return, and the CLI records the supplied facts.

The observation write command applies to legacy document sidecars only. The
semantic occurrence excludes checkbox state and physical line number.
Source/Acceptance/Artifact snapshots bind task applicability. Changed
target, label, context or bound values invalidate old observations. Latest
failure, revocation or equal-time conflicting observations leave the link
unverified. Check suppresses `LINK_UNVERIFIED` only for the eligible occurrence.
Arguments and time use exit 2, path errors 3, and stale, ambiguous or unsafe
writes 4. Legacy writes carry CAS and dry-run writes zero bytes.

`log context` and `log links audit` both return `link_verifications`, including
observations with no current matching link. An empty array means no decoded
observations. Malformed records appear separately in context's
`link_verification_errors` and audit's `errors`, and yield
`LINK_VERIFICATION_INVALID` in check. Each observation includes `source`
(`sidecar`, `legacy_metadata` or `legacy_history`), its original outcome and
binding, the matching current line when unique, `applicable` and
`invalidation_reason`. `target_status` reports the offline inspection result
(`ok`, `missing`, `outside`, `unreadable` or `external`). The two unified
history sources are read-only evidence. Their observations always have
`applicable: false`, even when the original link still matches. Audit uses
current observations and in-root existence checks for its current link rows
and delivery readiness.

## Lifecycle and maintenance command groups

See [lifecycle operations](lifecycle-operations.md) for state-set, workflow, run, closeout, retro and runtime command ownership, input schemas and limitations. All existing-document writes use the document/state token and support dry-run; run/runtime writes require the Thinking token. Workflow instantiate is create-only with exclusive file creation and a pinned template token; adapter binding remains pending. CLI commands do not execute skills automatically.

### Atomic workflow operations

`workflow update NAME --content-file FILE --expect-version TOKEN [--dry-run]` replaces one existing template after structural checks and CAS; preview includes the exact diff. It never changes companions or instances. `render` preserves declared YAML front matter and fills only explicit slots. `instantiate` checks the complete candidate at its output path, then publishes a complete new file without overwrite; bindings remain pending. Skill decisions, semantic review, source records and adapter bindings are separate steps. `workflow check` reports its structural-marker coverage, not semantic validity or real-use evidence.

`workflow create NAME --content-file FILE [--dry-run]` publishes one canonical `workflows/NAME/docs/NAME.md` in an existing approved directory. It previews the content, validates structural markers and refuses an existing template/output; absence is its create precondition, so no existing-file token is needed. It creates `lb/<name>.md.json` state, but no other directories or host document bindings.

## Concept-oriented routes

Use the [domain commands](domain-commands.md) for canonical task actions, optional candidate evidence, compatible dispatch attempts, runtime bindings, workflow lifecycle and skill usage. Old routes and option aliases are removed; use these command paths directly.

## Execution state in project JSON

`lb log execution context/record` reads and records attributed facts in
`<project>/lb/<name>.json`. The project is the nearest ancestor containing
`mind.yaml`, otherwise `--root`. Each record binds one Logbook and one Thinking by
project-relative path. Only records bound to the current Logbook are validated:
a malformed bound record, a missing bound document, two records binding the same
Logbook, a symlink or unparseable JSON in `lb/` is refused with the file name.
Records of other Logbooks and unrelated JSON are ignored. Dispatch, attempt and
agent-binding records live in Thinking’s `lb/` state section.

These commands record facts already established through the host. They do not
pause, resume, launch or hand execution to an Agent, and they never require
renewed human approval. Every fact is **caller-reported**: the CLI validates
structure and references, not truth. `runtime_transfer_verified` is always false.

### Target-file tokens and a minimal recording workflow

Run from the coordination root and keep input files inside it; `/tmp` inputs are
refused. Extract tokens from context JSON programmatically.

| Write | Token source | Protected file |
| --- | --- | --- |
| `log execution record LOG` | `log execution context LOG --json`: `version_token` | Execution JSON |
| `dispatch create LOG --thinking THINKING` / `agent bind` | `log context THINKING --json`: `version_token` | Thinking and its `lb/` state section |
| `agent send LOG --thinking THINKING` | Thinking token plus execution token as `--expect-execution-version` | Thinking precondition and execution journal |
| `log sync LOG` / `task note LOG` | `log context LOG --json`: `version_token` | Logbook Markdown and its `lb/` state section |

Example: record an existing release instruction, then prepare the remaining
package. Neither command sends a message:

```sh
(
  set -eu
  lb log execution context log.md --json > .execution-context.json
  lb_json_token=$(python3 -c 'import json; print(json.load(open(".execution-context.json"))["version_token"])')
  lb log execution record log.md --input-file facts.json --expect-version "$lb_json_token" --json

  lb log context thinking.md --json > .thinking-context.json
  lb_thinking_token=$(python3 -c 'import json; print(json.load(open(".thinking-context.json"))["version_token"])')
  lb dispatch create log.md --thinking thinking.md --input-file dispatch.json --expect-version "$lb_thinking_token" --json
)
```

A successful write returns the token for the next write to the **same** document/state pair (or execution JSON);
dry-run returns the unchanged token. On a conflict, reread the named context and
review the changes; do not loop on refreshed tokens or use another file's token.

The first record requires `thinking` and `facts`. `name` defaults to the Logbook
file stem, `advancement` to `name` and `captain` to `captain`; repeated identity
fields must match. Later inputs need only `facts`. An absent record has the token
of empty bytes; `log context` also reports it under `execution`. Replaying an
identical fact ID changes nothing; different content under an existing ID is
refused.

```json
{
  "thinking": "projects/example/thinking/delivery.md",
  "facts": [
    {
      "id": "instruction-2", "kind": "takeover", "origin": "explicit",
      "source": {"kind": "human_instruction", "ref": "conversation message 2"},
      "release_condition": null
    },
    {
      "id": "ownership-1", "kind": "ownership", "takeover_id": "instruction-2",
      "source": {"kind": "runtime_observation", "ref": "current ownership inspection"},
      "owner": "captain", "conflicts": false, "settled": true
    }
  ]
}
```

Sources are `{kind, ref}`; `verified_result` also requires `verifier` and `subject`.

| Fact kind | Other required fields | Meaning |
| --- | --- | --- |
| `takeover` | `source`, `origin: explicit/automatic`, `release_condition` | Restricts delegation for the whole advancement. Explicit origin requires `human_instruction`. |
| `ownership` | `source`, `takeover_id`, `owner`, `conflicts`, `settled` | Only a runtime observation with no conflict and settled operations yields a reported owner. |
| `condition-result` | `source`, `takeover_id`, `condition_id`, `satisfied` | Verified check of a previously authorized release condition, not a new grant. |
| `delegation-release` | `source`, `takeover_id`, `recipient`, `scope`, `condition_result_id`, and `task_id` for `task` or `dispatch_id` for `dispatch`/`advancement` | Human instruction (`condition_result_id: null`), or caller judgment citing a satisfied condition result. |
| `handoff` | `release_id`, `receipt`, `execution_ready`, `monitor_ready`, `ownership`, and `operation_id` for a Task release | Post-operation observations; never performs delivery. |
| `transport-resolution` | `source`, `operation_id`, `outcome: submitted/not_submitted` | Resolves an unknown send; never retries it. |

`release_condition` is null or an object with `id`, `source`, `recipient`, `scope`
and the same target field as the release. Explicit takeover requires a human
instruction. An automatic takeover condition can release its nominated Task or
Dispatch. A release through a condition must match its recipient, target and
scope exactly. Automatic takeover cannot replace a retained explicit restriction.

Each `handoff` observation is `{status, source}`: receipt `accepted/unknown/rejected`,
readiness `ready/unknown/not_ready`, ownership `recipient/captain/unknown/conflict`.
Accepted receipt, both readiness values and recipient ownership, all from runtime
observations, produce `handoff_reported_complete`.

For a Task handoff, `task agent send` records the current release with the
operation. Cite that operation ID when recording acceptance, readiness and
ownership. Its send must belong to the same Task, recipient and current Binding.
Verify unknown delivery before recording acceptance or transfer. Replacing a
release or Binding invalidates the prior handoff as evidence of current ownership.
For a Task release, the execution context's reported handoff owner applies to
`release.task_id`. A release for another Task preserves ownership of this Task.
Legacy Dispatch releases retain their recorded target and apply to Dispatch commands.

Task completion, skill changes and recovery do not clear the restriction. A
release opens only its nominated target and recipient; an advancement release
lifts the restriction once its handoff is reported complete. A later ownership
fact clears that handoff report. Unknown send operations block all delegation.
`dispatch create`, advancement transitions, attempt start and `agent send` check
these constraints; inspection, cancellation and return are always allowed. A
required independent review stays pending; Captain self-tests do not satisfy it.
A legacy Captain marker without JSON blocks delegation until reconciled.

### Runtime send and recovery

`agent send` performs a real operation. It requires `--operation-id ID`,
`--expect-execution-version JSON_TOKEN`, the Thinking token, session/observation
and message-file inputs; there is no `--basis`. Without an execution record it
creates one with default identity and empty facts, which asserts no takeover.

After live preconditions and immediately before transport, send persists an
unknown intent with recipient/session and message/package digests; if that fails,
nothing is sent. Success persists the receipt, which proves submission only. A
repeated successful ID returns the saved receipt without sending; a changed
payload under that ID is refused, and another ID cannot resend a dispatch with a
submitted or unknown operation. Dry-run inspects live state but writes and sends
nothing.

On timeout or interruption the outcome stays unknown. Inspect the runtime and
record `transport-resolution` with delivery evidence; an idle recipient is not
proof of non-delivery. Observed non-delivery permits a new operation ID under the
existing permission; observed delivery never permits a resend. If transport
succeeds but the receipt cannot be saved, send exits 4 with the actual receipt and
`record_saved: false`. There is no automatic retry or exactly-once guarantee.

### Records, presentation and limits

Context derives `reported_owner`, delegation constraints, `reply_prefix` and
`page_projection_matches`. JSON never edits Markdown: repair the page marker with
fresh Markdown CAS and `log sync`, and task facts with protected task notes.

Cooperating local writers share a nonblocking `lb/.lock` (macOS/Linux) plus file
CAS. It is not a distributed lock or a transaction across runtime, JSON and
Markdown; manual edits and direct host tools bypass it. The host still owns
authorization, evidence truth, safe pause, monitoring and independent review.


## Canonical Task actions

`task complete|pause|resume|block|unblock LOG TASK_ID` uses `--basis`,
`--expect-version`, `--dry-run` and `--json`. Block also requires `--reason`;
resume without a recorded prior state requires `--to pending|active`.
Completion requires no Run, submission or fabricated start event. Human tasks
remain protected. These actions preserve history and derive current state from
Markdown plus validated disposition records, without a duplicate current status.
Resume reads the prior state from the task record in `lb/`. Blocker remains in
Markdown. Current Task dependencies come from the Run's authoritative graph.
Cancellation and reopen preserve readable reasons and
structured historical evidence. See [document and Task authority](document-state.md#read-and-edit).

`task migrate LOG --expect-version TOKEN --dry-run --json` previews supported
legacy mappings and inline Resolution/Resume conversion; omit `--dry-run` to apply with the same token. Consistent
accepted/submitted become Markdown-derived done/active, with prior evidence
retained. Conflicts, ambiguous skipped states and unsupported ownership/parent
mappings refuse apply; resolve those explicitly before retrying. Reads do not
silently migrate legacy records. Existing legacy submission/acceptance routes
remain available and retain candidate checks.

Legacy sidecar dependencies remain visible and constrain legacy start actions.
Before canonical actions or replacement, explicitly migrate remaining sidecar
dependencies and resolve unsupported ownership/parent mappings. Migration also
handles records whose status is already canonical but whose dependencies remain
in the sidecar. Conflicting dependency sources refuse writes.

Replacement requires every referencing task to have an identity so its dependency
mapping can be explicit; use `task identify` on an unidentified dependent first.
Both split forms preserve the original prerequisites in each replacement. Archived
task IDs cannot be assigned to new work. On an interrupted Run replacement,
preview `log recover LOG --dry-run` and apply with its `--expect-version` token.
Then run `log sync-state` for the changed Logbook.


## Agent wait and event handling

Managed observation has three objects: Observation owns targets/cursors, Event owns
handling, and Answer owns a delivery attempt. The commands below do not complete
business Tasks or grant execution permission.

| Object | Command | Purpose |
| --- | --- | --- |
| Observation | `agent observation context LOG --json` | Read state, unresolved Events, pending Answers, capabilities and version_token |
| Observation | `agent observation configure LOG --input-file FILE --expect-version TOKEN` | Explicitly configure targets after listener exit |
| Observation | `agent wait --log LOG --timeout SECONDS --expect-version TOKEN [--stream]` | Observe configured targets with one owned listener |
| Event | `agent event defer LOG EVENT --action-id ID --input-file FILE --expect-version TOKEN` | Retain unresolved work with reason and responsible_party |
| Event | `agent event resolve LOG EVENT --action-id ID --input-file FILE --expect-version TOKEN` | Assess non-question work, or record an evidenced obsolete question |
| Answer | `agent answer submit LOG EVENT --operation-id ID --input-file FILE --expect-version TOKEN` | Save intent and submit through a supported native question protocol |
| Answer | `agent answer reconcile LOG OPERATION --expect-version TOKEN [--input-file RECEIPT]` | Check delivery evidence without sending |
| Answer | `agent answer prepare LOG EVENT --operation-id ID --input-file FILE --expect-version TOKEN` | Save external intent before a separately authorized manual/UI action |

Prefix each command with `lb`. All managed mutations require the SHA-256 token from
Observation context, including absent-state configure. Document and execution tokens
are not interchangeable. Context is read-only; missing state is not created. Missing
stable document identity requires explicit existing document migration. Mutations
support --dry-run: no files, listener or external mutation; a preview reserves nothing.

Configure input is exactly `{ "targets": [...] }`. Each nonempty target wraps the
full native identity in **`binding`**, with an optional sibling **`baseline`**;
identity fields placed directly on the target are invalid. The same input shape
applies to new-run `agent monitoring configure`:

```json
{
  "targets": [
    {
      "binding": {
        "machine": "local",
        "server": "default",
        "workspace_id": "w1",
        "tab_id": "w1:t2",
        "pane_id": "w1:p2",
        "agent_id": "codex",
        "session_id": "native-session-id"
      },
      "baseline": {
        "state": "working",
        "observed_at": "2026-01-01T00:00:00Z"
      }
    }
  ]
}
```

Replace the example identities with values observed on the selected server.
`agent_id` is the native runtime Agent identity, not the Task assignee subject ID.
Omit `baseline` unless its state and timestamp were actually observed; never invent
or reset a baseline. `server=default` applies only to a running unnamed server.
Configure retains unaffected and retired cursors
and unresolved Events. Reordering is a no-op, known baselines cannot reset, and a
terminal identity cannot be rearmed after retirement. Listener and affected binding
action locks exclude unsafe target changes; unknown/submitted Answer delivery blocks
removal. Stop the host-owned listener and verify actual exit before reconfiguration.
Saved PID/status is diagnostic, never ownership proof.

One-shot wait returns reason, invocation_id, new_events, unresolved_events,
pending_answers and version_token. Event and cursor commit atomically before output;
no-event working re-arm also persists. Lost output is recovered through context.
Already-reported unresolved work does not retrigger notifications. Another listener
refuses while the real lock is held. SIGINT/SIGTERM clean only owned waiting children;
a later exclusive admission records an abandoned gap after forced loss.

For a submitted `task agent send`, managed wait can detect a completion between
samples. It compares the native completion sequence with the pre-submission
sequence from the receipt for the verified binding and terminal. Repeated samples
and listener resumes do not repeat that notification. An older idle snapshot
cannot settle the new send. If continuity cannot be established, managed wait
reports an `observation_gap` or an identity change. A `settled` event is a runtime
notification for Captain to inspect. Task acceptance still requires its own evidence.

A busy cooperating writer lock during a sample commit or listener end is retried
within the same wait deadline. The listener retains the original sampled cursor
and Events and checks its saved generation and targets on every attempt. A
signal stops waiting for a busy writer. If contention persists, exit 4 identifies
whether the sample or the listener end remains unsaved. Read fresh context for
durable Events. An unsaved sample leaves the listener marked active so the next
exclusive admission records a gap.

Live --stream emits compact flushed JSONL locators after commit: type=event,
observation_id, invocation_id, event_key, kind, target_key and version_token. There
are no heartbeat snapshots or transcripts and no trailing pretty-JSON result.
One listener_end reports timeout/cancelled/failed where output remains usable.
Broken stdout stops observation with cleanup; saved work remains. A notification's
token may already be stale, so read fresh context before handling.

Defer input is reason, responsible_party and optional evidence references. Resolve
input is assessment plus optional evidence for non-questions, or obsolete plus
nonempty evidence for withdrawn/superseded questions. Plain resolve cannot assert
answer confirmation; uncertain Answer delivery blocks obsolete closure. Action ID
and canonical content replay without writes; conflicting content refuses. New actions
on resolved Events refuse. Caller cannot provide adapter provenance.

Automatic submit input is question_id, revision and answer. Unknown intent and answer
digest persist before sending; raw answer text is not stored. The current Herdr adapter
supports explicitly configured local Claude Code AskUserQuestion hooks. Without
that native callback it refuses with capability_unavailable, or identity_missing
for incomplete native bindings, before intent/send. Ordinary prompt or send-keys
is never an automatic-answer fallback. Codex question answering remains unmapped.

For the optional Claude integration, both coordinator and worker inherit
LBKIT_CLAUDE_QUESTION_DIR pointing to the same short, absolute, owner-only directory.
The consuming repository explicitly configures PreToolUse and PostToolUse command
hooks matching only AskUserQuestion, invoking its installed environment's
`python -m logbook_cli.claude_native_hook`; give the PreToolUse command a timeout
of at least 130 seconds. Installation does not modify project/global Claude settings.
These callbacks do not approve other tools. They require the worker's independently
observed Herdr native session to match the actual callback session_id.

While the native PreToolUse callback is waiting (at most 120 seconds), bounded
local socket inspection augments the observed needs_input Event with question.id,
question.revision and question.questions. This works even while Herdr sees the hook
UI as working; expired/unreachable callbacks do not override native UI observations.
Use those saved identifiers in submit. A single question accepts a nonempty string;
multiple questions require an exact question-text-to-answer-string object.
Callback acceptance alone leaves delivery unknown. Only matching native PostToolUse
structured answers confirm delivery and atomically resolve the Event. For this
hook protocol, PostToolUse must carry the same session_id/tool_use_id and the
PreToolUse updatedInput as tool_input. Its structured tool_response includes
`questions` equal to updatedInput.questions and `answers` equal to
updatedInput.answers (an exact question-text-to-answer-string mapping). Omitted or
mismatched questions/answers are not confirmation; a zero hook exit alone does not
prove that a receipt was created. Missing or
late confirmation stays unknown and blocks new operation IDs; reconcile without an
input file probes the saved native receipt without sending again.

The runtime holds sockets and bounded correlation/digest/receipt records, with no
copied transcripts, drafts or raw answers. It reserves a receipt per accepted
question, up to 1024 questions; capacity exhaustion refuses before release. Retain
this directory while any delivery is uncertain. Rotate it only after all pending
answers are reconciled and hooks/listeners have stopped. Socket paths must fit the
platform's Unix socket limit; a short mktemp directory under /tmp is suitable.
This opt-in local callback protocol adds no public CLI command or configuration
format change. Live host/runtime acceptance remains separate from fixture tests.

External prepare input is answer_digest, execution_owner, nonempty evidence and
optional question_id. It stores external unknown and sends nothing. It cannot be
converted into adapter mode or bypass another pending attempt. Reconcile accepts a
receipt with receipt_id, outcome (submitted/confirmed/not_submitted), answer_digest,
matching question_id when present, and nonempty evidence. Supplied receipts remain
caller-attributed; a native probe remains adapter-attributed. not_submitted additionally
requires affirmative non_submission evidence and, for external execution,
executor_terminated=true. Idle, timeout and lock possession are not evidence of
non-submission. Confirmed receipt and Event resolution commit together. Same operation
is replay before live question checks; a new ID cannot bypass uncertain delivery.

State is private consumer runtime data at `project/lb/observations/<document-id>.json`.
The cooperating single-location transaction uses safe no-follow directory descriptors,
writer exclusion, CAS, atomic replacement and fsync. Directory fsync failure after
replace is uncertain persistence: the writer returns persistence_failed (exit 3);
reread actual state and do not assume nothing changed. Transport uncertainty keeps
unknown/submitted delivery, while persistence errors are never a successful receipt.
Input is bounded to 1 MiB; encoded state to 8 MiB, Events/Answers to 4096 each,
transitions to 8192, encoded transition/completion records to 16 KiB, summaries/reasons
to 4 KiB and evidence to four references of 2 KiB each. Admission reserves a complete
target batch, pending Event/Answer completion and 64 KiB lifecycle/error space; it
refuses before exhaustion without eviction. Distributed copies and raw callers are
outside managed ownership guarantees; disk failure can still prevent persistence.

### Host waiting and recovery

Claude Code prefers native Monitor running managed wait --stream. Foreground managed
wait is the fallback; preserve the same live handle across host yields and use finite
supported deadlines. Host expiry, notification delivery and actual Captain handling
are separate observations. A bounded quiet interval does not prove zero model turns.
Record inner/outer requested/effective windows and all model continuations.

Test Monitor background input, input during a suspended foreground call and input
between calls independently. Post-turn wake requires final before wait completion,
a new unprompted Captain turn and an actual handling receipt. A PID, badge, tool
completion or manually resumed turn proves no automatic wake. Do not create a daemon
or monitor Agent to substitute for missing host behavior. Unsupported facilities stay
explicit; they are not successful positive acceptance.

### Raw compatibility

`lb agent wait --input-file FILE --timeout SECONDS --json` remains bounded/read-only.
Keep complete next_input (targets, opaque after and unresolved_events). The carry list
is bounded to 256 and does not provide managed persistence or a global listener lock.
Legacy requests remain accepted; older binaries may reject additive continuation
fields. Pin the observer revision with raw checkpoints. Managed --log forbids
--input-file; raw mode rejects --stream, --expect-version and --dry-run. No package,
skill or configuration version is automatically changed by this additive API.

## Route confirmation and task readiness

Use `lb log route LOG --json` to read the reviewed scope, its `route_ref` and
each task's `criteria_digest`. To record decisions or preflight observations in
an explicitly bound Thinking document, use
`lb log record-readiness LOG --thinking PATH --input-file FILE --dry-run --json`.
Apply with the same inputs after reviewing and then explicitly synchronize the
saved Thinking document. The input carries `run_ref` (the run ID) and arrays
`confirmations`, `observations` and `grants`. Preserve each existing array as a
prefix of the updated array.

All readiness records carry a nonempty string `source` and a `route_ref`.
`record-readiness` refuses newly added records whose source is missing, blank
or a different JSON type, including in dry-run. Previously saved rows remain
readable as history, subject to the existing readiness applicability checks.
Execution facts use their own source schema. A confirmation uses status
`confirmed`. A ready observation uses `task_id`, status `ready`,
`criteria_digest` and `skills` (verified applicable names, or an empty list
for built-in work). A task observation may specify `action` as `dispatch` or
`takeover`. Omit it to apply the observation to both actions. A record can
supersede an observation only within the same action scope. Common blockers
apply to both actions and a ready observation for one action cannot make the
other ready. Route-wide observations omit `action`. Blocked observations can supply `object`, `owner`,
`clear_when` and `human_action`. An authorization uses `task_id`, `actor`
(the executor subject ID), `action` (`dispatch` or `takeover`) and status
`granted` or `revoked`. Record decisions and observations from their actual
sources. The CLI checks their applicability to the current route.

Query `lb log readiness LOG --task-id ID --actor ACTOR --action dispatch --json`.
A confirmed route can enroll a Task for self-checks through
`lb log preflight-plan LOG --task-id ID --input-file FILE --expect-execution-version TOKEN`.
The input carries `actor`, `scope_ref`, `candidate_ref` and `checks`. Each check
lists a unique `check_id` and a `subject_id`, which may be null while selection
is pending. A current sourced `preflight-plan` grant for that Task and actor
must match the candidate and the complete check list in check-ID order. An
authorized empty list explicitly records that no Sailor checks apply. Resolve
conflicting current grants before saving or using a declaration. Preview
with `--dry-run` and use the current execution token when saving.

An approved runnable check includes its `instruction` and can name a
`binding_task_id` for a separately assigned Sailor. To check before a Task Binding
exists, include `environment: {binding, working_directory}` in the approved check.
The binding names the machine, server, workspace, tab, pane, agent and native session.
The CLI verifies identity and the absolute working directory against the live target.
If a Task Binding is added for that same environment, current evidence remains usable.
Send a preparation check
with `lb agent self-check LOG --input-file FILE --expect-execution-version TOKEN`.
The input names `task_id`, `check_id` and `operation_id`. The CLI resolves the
approved subject's binding and journals the send before prompting the session.
Keep the same operation ID when inspecting an uncertain result.

`lb log preflight-observe LOG --input-file FILE` reads a reply using an input
containing `operation_id`. The current reply adapter checks the owned local
Codex session journal against the live binding or approved environment. It accepts a
completed assistant message for the exact preparation prompt and returns the
Sailor's checked condition alongside the result. The temporary cache is keyed
by the normalized Logbook project root and run ID. Results expire after 30
minutes. If a still-current reply was previously cached under the invocation
root, collect it again using its existing operation ID. A known submitted
check with no usable reply can be sent with a new
operation ID 30 minutes after the original intent. An unknown delivery still
requires reconciliation.
An unsupported host leaves the check unverified. The send journal and temporary
cache have separate lifetimes.

A blocked result provides recovery steps. Reconcile unknown operations before
another attempt. New sends require applicable evidence. For an existing run,
reuse verifiable decisions and collect missing preflight evidence before a new
dispatch. Existing submitted operations retain their replay behavior.

Record an observed action through `lb log execution record` using a
`business-action` fact with `id`, the submitted `operation_id`, `outcome`
(`started` or `not_started`), and a `source` of kind
`runtime_observation` referencing the actual evidence. A submitted receipt
with no action evidence requires reconciliation before a new send to the
task. Replaying the same operation still returns its saved receipt.
Follow-up instructions on the same binding after an observed first action
use the existing live identity, delegation and delivery guards. The first-start
readiness and build checks apply again on a replacement binding.

Before a first-start delegation handshake, the sender compares its CLI version
and implementation digest with the recipient's. `lb --build-identity` reports
both in JSON. The implementation digest covers the installed CLI Python
sources. It distinguishes CLI implementations that share a development version.
Keep the skills and contracts pinned to the intended candidate separately.

For a new first send, verify the launcher's absolute executable path in the
recipient's actual work context and record it as `work_context.cli_launcher`
in the Task binding. Use the same launcher on the recipient. A compatible
local Dispatch uses `cli_launcher` in its agent binding. Existing records
without the path remain readable and replayable. Supply a current binding
with the path for a new first send. The CLI invokes the recorded executable
directly, with the verified work directory, and checks its response.
A version string alone cannot prove the implementation. A missing or
different version or digest blocks the handshake, intent write and business
send. The refusal includes known versions and implementation digests.

A remote Task uses the enabled Herdr machine profile with a matching server
scope. The probe uses that profile's saved SSH target with noninteractive
authentication and a known host key. Identity inspection and control use its
stable profile ID. After updating from a label-based observation, inspect
again for a current token. Remote legacy bindings without a verified server
scope use a current Task binding for a new send.

Before writing action-specific observations in a shared run, compare
`--build-identity` from the actual launchers that can start work there. Older
clients read action-specific observations as common evidence.

Readiness evidence can include stable `id` and an explicit `supersedes` for a
same-scope record. Observations can supply an `inputs` map from project-relative
file keys (for example, `inputs/candidate.json`) to SHA-256 digests. Use keys
without absolute prefixes or parent traversal. The CLI checks new declarations
and rereads applicable inputs for readiness, dispatch and takeover. An input
that is missing, has changed, escapes through a symlink or belongs to a nested
project cannot support readiness. Always resolve the saved key from the
Logbook project root. Preserve historical observations and collect fresh
evidence for in-flight observations recorded under the old invocation-root
interpretation. For an environment-specific observation, `machine` pins it to
the dispatch binding's machine or to `local` for Captain execution.
`expires_at` accepts a timestamp with timezone, after which the observation
requires rechecking. A revoked authorization remains effective until explicitly
superseded in the same authorization scope.

Captain first start uses `lb log takeover-start LOG --task-id ID --actor ACTOR
--operation-id OP --expect-execution-version TOKEN --transition reserve --json`.
A successful new reservation returns `may_start: true`. Resolve the same
operation with `--transition started` or `--transition not_started` and
`--evidence SOURCE`. An existing reservation returns `may_start: false`.

The route query also returns `source_digest` for auditing and `task_scopes`
for an explicitly reviewed Task scope. An evidence row with `scope` equal to
its Task ID uses the corresponding task scope digest as its `route_ref`.
Authorized directories contribute their contents and order. Their line numbers
locate source text. Explicit Stage goals contribute to the route and relevant
task scopes. Top-level label spacing and list markers are normalized for goal
comparison, including up to three leading spaces on a top-level goal.
Indented notes inside Tasks and ordinary list items do not supply Stage goals.
A column-zero HTML comment or fenced block ends an indented Task body.
Hidden comment and code contents do not supply goals. A Markdown thematic
break takes precedence over a list marker, so a following top-level goal
remains in scope. A list goal can follow one to four columns of whitespace
after the marker. Indented code inside a list item does not supply a goal. Recheck affected confirmations after a scope change. When the
original reviewed text proves the decision covers the current scope, an
authorized operator can record it against the new reference with its original
decision source. When coverage is unclear, obtain confirmation of the
affected scope. Preserve previous decisions and revocations.
A whole-route decision uses the output's top-level `route_ref`. A Task scope
includes its position, preceding work and transitive dependencies.
