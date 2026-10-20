# `lb`: the guarded lightweight Logbook CLI

`bin/lb` uses Python 3.11+ and Click, with a uv-locked environment, built for structured reading of this repo's Markdown conventions and minimal-scope edits. It is not a scheduler: it never accepts delivery, dispatches work, presumes authorization, or reorders checklist items, and it never touches the network.

```sh
# Discover conservatively recognized main logbooks (default scan: projects/*/docs/*.md)
bin/lb list --json
bin/lb list --projects-dir records --json  # maps to the host's documents.project_root

# Read stages, next item, working directories, links, and the concurrency version token
bin/lb context projects/example/docs/logbook.md --json

# Check one logbook, or check all discovered logbooks
bin/lb check projects/example/docs/logbook.md
bin/lb check --all --json

# Structured state snapshot (derived summary, stage counts, 🔮 gate, top status-line ownership)
bin/lb state projects/example/docs/logbook.md --json

# Sync delivery-stage H2 emoji and the adopted top status line; inspect a dry run first
bin/lb sync projects/example/docs/logbook.md --token 0123... --dry-run

# Pass the version_token returned by context unchanged into precise write operations
bin/lb task update projects/example/docs/logbook.md \
  --stage 'Stage 01 实现' --task '开发：实现 CLI。 @logbooks 🤖️' \
  --status / --token 0123... --dry-run
bin/lb task artifact projects/example/docs/logbook.md \
  --stage 'Stage 01 实现' --task '开发：实现 CLI。 @logbooks 🤖️' \
  --artifact '产物：[CLI](../bin/lb)' --token 0123...

# Append a todo to a confirmed stage, or place it before an existing todo in that stage
bin/lb task add projects/example/docs/logbook.md \
  --stage 'Stage 01 实现' --text '测试：验证 CLI。 @logbooks' --token 0123... --dry-run
bin/lb task add projects/example/docs/logbook.md \
  --stage 'Stage 01 实现' --text '测试：验证 CLI。 @logbooks' --before-line 42 --token 0123...

# Append one short fact under an agent todo; kind is one of 产物, 阻塞, 状态, 交接
bin/lb task note projects/example/docs/logbook.md \
  --stage 'Stage 01 实现' --task '开发：实现 CLI。 @logbooks 🤖️' \
  --kind 阻塞 --text '🚨 请人类负责人完成登录；登录后恢复。' --token 0123... --dry-run

# Append one Markdown link to a stage's 相关链接： block (created before 待办： when absent)
bin/lb link add projects/example/docs/logbook.md \
  --stage 'Stage 01 实现' --link '[PR #12](https://forgejo.example.com/o/r/pulls/12)' --token 0123... --dry-run

# Rewrite link targets by prefix, e.g. after merging a worktree; every rewritten target must exist
bin/lb link rewrite projects/example/docs/logbook.md \
  --from 'file:///Users/me/ws/app/.worktrees/feat-x/' --to 'file:///Users/me/ws/app/' --token 0123... --dry-run

# Human todos only, or just the next item
bin/lb task list projects/example/docs/logbook.md --human --json
bin/lb task list --status in-progress --json
bin/lb task next projects/example/docs/logbook.md --json

# Optional repository-root lbkit-skills.json (JSON Schema: .lbkit/schemas/lbkit-skills.schema.json, referenced by the file's leading "$schema" key, with "version" as the format version, currently only 0.1.0): registers skill chains by kind of work; fields name, scope (usage range), chain, actions (action-prefix hints), companions (companion skills: skill + when), description
bin/lb skills --json
bin/lb skills --action 开发 --json
bin/lb skills add --name 'speckit 功能实现' --scope '适用：…；不适用：…' --chain speckit-implement --action 开发 --companion 'comment-prune=实现完成、提交前' --dry-run   # keeps an existing file's plain indent-2 JSON layout; otherwise writes scalar arrays on one line
bin/lb skills usage --since 2026-10-01   # skills actually invoked in Claude Code and Codex sessions; the only command reading outside --root (~/.claude, ~/.codex), counting only sessions whose working directory falls in a logbook-registered directory or this repo
bin/lb skills extract --json   # 「技能：」 sub-lines not covered by any entry (skill chain or companion skill), listed verbatim with the todo's original text, completion status, and the work package pointing back to it
```

`--root` defaults to the current directory and can confine every path to a synthetic repository or worktree:

```sh
bin/lb --root /tmp/fixture context projects/demo/docs/log.md --json
```

`check`'s `DUPLICATE_TASK_TEXT` flags unclosed same-text tasks within one Stage (historical duplicates that are all checked no longer warn) — a preview that later write commands targeting the task's original text will be rejected as ambiguous. `local_target` runs expanduser ownership judgment on links starting with `~`; those outside the root still count as LOCAL_LINK_UNVERIFIED.

The "next item" in `context`, `state`, and `todo` is computed only from unfinished (`[ ]` or `[/]`) todos in `Stage NN` delivery stages (`NN` may carry one letter suffix, e.g. `Stage 03b`); global checkbox lists in an old logbook's Overview take no part in scheduling.
`task list` and `task next` use the same delivery-stage scope; `task list` filters by stage, status, and human ownership, and lists todos across all discovered logbooks when the logbook path is omitted.

Discovery defaults to `projects/*/docs/*.md` inside the root; `list`, `check --all`, and `task list` accept `--projects-dir` to pass in the host-configured `documents.project_root`, and recognize candidates with the heuristic "exactly one visible H1, plus an H2 stage or a todo"; this excludes `thinking/` and `prompts/` but is not a semantic classifier for arbitrary articles. The `projects`, project, and `docs` directories all get containment checks before traversal; directories pointing outside the root or otherwise anomalous are not traversed. Headings, todos, and links inside code fences and HTML comments do not participate in parsing; a trailing HTML comment hides only the comment itself, so a task before the comment keeps its full original text and updatable identity. If a multiline comment's closing line is followed by structural text, `COMMENT_STRUCTURE_AMBIGUOUS` is reported rather than guessing the parse. A fence closes only with a fence of the same character, sufficient length, and nothing but whitespace at end of line. `context.stages[].tasks` gives each item's original text, status, line number, repository marker, and human marker. `bound_records` lists only places in the body that explicitly link to `thinking/` or `prompts/` — bindings are never guessed from same-named files.

## Write and Concurrency Protection

Every write operation (including `sync`) must supply the SHA-256 `version_token` returned by `context --json` or the preceding successful write. Any single-byte file change, or a stage and task original text that cannot be uniquely matched, refuses the write with exit code 4; an invalid status value is a parameter error with exit code 2. Tasks are located by the stage heading (minus the status emoji) plus the full original task text — never by line number. `task update` allows only `[ ] → [/]` on `👱` or `人工验证：` human items; completion, cancellation and reversal remain refused; `task artifact` and `task note` refuse to write sub-lines onto human-owned items, except `task note --kind 状态` (`Status`), which appends a status sub-line and leaves the first line and checkbox untouched. `task add` creates only not-started items and rejects same-text todos in the same stage; `--before-task` matches exact task text uniquely in that stage; it is mutually exclusive with legacy `--before-line`, which must point to a task first line. Line numbers shift after every insert, so repeated `--before-line N` with the same N places each later item before the earlier one; use `--before-task` with the same anchor text to keep insertion order. Before using `task add`, an agent still needs the human's explicit confirmation of the new items and their order. `--dry-run` writes nothing and prints a reviewable unified diff (the JSON `diff` field).

All write commands re-parse the candidate text before writing and reject newly introduced deterministic `check` issues (such as missing in-repo links). Pre-existing issues do not block unrelated local updates; transient stage emoji, explicit `[-]`, unfetched external links, and unverified local links outside the repository count as permitted notices. The `issues_introduced` field of the JSON write result is an empty list when admission passes. `task artifact` and `task note` place new sub-lines after the existing indented sub-items; appending a duplicate is refused when an identical sub-line already exists. `task artifact` prepends the `产物：` (`Artifact:`) label when the text does not already start with it. When `task note` text starts with `🚨 ` and a `--kind` is given, the marker stays at the very front of the sub-item body.

Before writing, the tool re-checks root containment and the source file's bytes after fsyncing the temp file and before `os.replace`, then performs the same-directory atomic replacement. This narrows the clobber window of ordinary concurrent editing but is not a CAS/lock guarantee against arbitrary editors or malicious processes; on conflict, still re-read context after the refused write.

Paths resolve symlinks on both read and write, and targets must still lie inside `--root`. The exception is read-only `skills usage`: it reads session records from `~/.claude/projects` and `~/.codex/sessions`, reporting only sessions whose working directory falls in a logbook-registered directory or this repo. Edits preserve UTF-8, the original CRLF/LF style, and all untouched bytes; `sync` only changes the H2 emoji of delivery stages whose status is determinable — empty stages, unresolved `[-]`, and unknown statuses are never silently judged complete. An unresolved `[-]` is reported by `check` as a skipped record, neither an approval signal nor a blocker: `next_task` skips it and advancement continues with the next unfinished item; a valid task disposition permits closure without claiming acceptance.

## Checks, Status, and Limits

`check` reports issues in the format `路径:行号:代码:说明`, with `--json` returning the equivalent structure. Exit codes: 0 no deterministic issues (there may still be `LINK_UNVERIFIED` notices), 1 deterministic issues found, 2 command parameter error, 3 path/read refusal, 4 concurrency or write-protection refusal. HTTP(S) links are only reported as `LINK_UNVERIFIED` — the network is never touched; local links are checked only for existence within the root. The tool parses no arbitrary YAML and validates nothing about external files, remote links, or mind-forge metadata.

External URLs (such as Forgejo PR links) report `LINK_UNVERIFIED` by design — a deterministic notice, not a structural error; a PR link is the run instance's identity notation, so keep it and never downgrade the link to plain text just to clear the notice.

## The 🔮 preflight gate

When any todo's or indented sub-item's checkbox text contains `🔮` (a pending-discussion blocker produced by lb-preflight and written in after human confirmation), the whole logbook is considered halted:

- `context --json` returns `preflight_blockers` (each with `line`, `text`, `indent`, `stage`) and `preflight_clear: false`; each task's `preflight` boolean marks whether that line is a blocker.
- `check` reports `PREFLIGHT_BLOCKER` for every 🔮 checkbox line (a deterministic status record, same class as `[-]`'s `SKIPPED_EXPLICIT`, contributing to exit code 1).
- `sync`, `task update`, `task artifact`, `task add`, `task note`, `task rewrite`, `task split`, `task resolve`, `link add`, and `link rewrite` all refuse to write with exit code 4, with the error naming the line; the CLI offers no bypass flag — the only way out is a human rewriting or removing the 🔮 in the logbook text, then re-fetching `context`.

The tool only detects markers and does not verify a 🔮's provenance; write and adjudication semantics are in [Logbook Format](logbook-format.md) and the lb-preflight SKILL.

## Top Status Line and Structured State

Manage status emoji through this script first; do not hand-edit H2 emoji or the machine-readable status segment. `state --json` gives a structured snapshot: overall counts (delivery stages done/in_flight/not_started), `summary` (the derived machine-readable string), `next_task`, the 🔮 gate, and the `owned` attribution of every `> 状态：` line.

The top `> 状态：` line splits at the first `——`: the first half is the machine-readable segment, which `sync` rewrites to the derived string when it starts with 🛫/🚧/✅ — `状态：<emoji> <首个未验收交付阶段> · [🔮 待讨论 N 项 · ]下一项：<待办原文>` (or `状态：✅ 全部交付阶段已完成` when everything is done) — reported as `summary_updated` / `summary_kept_human`; the second half, the human commentary, is preserved verbatim. Narrative lines that do not start with an emoji, or that lack the divider, are treated as human prose and never touched, and no status line is auto-created for logbooks without one.

Running tests:

```sh
uv run --locked python -m unittest discover -s tests -v
```

## Removed companion view

`lb todo` is no longer supported. Use `task list`, `task next`, `context` or `state`; human-readable summaries belong in the response. Protected writes never create or refresh TODO.md or a replacement view. Existing consumer files are preserved.

## Skill Integration and Evaluation

lb-* entries call the CLI at their respective steps; the shared flow is in [document adapters](../../skills/lb-update/references/document-adapters.md#cli-invocation-in-this-repository): plan reads and checks, push marks in progress after taking a task, status queries and syncs authorized emoji, update updates status and artifacts after evidence acceptance; preflight is a read-only analysis entry, with blocker write-back done by the skill within the logbook write boundaries — never through CLI write subcommands. The script neither runs these skills itself nor checks task authorization or evidence sufficiency.

`tests/test_lb_skill_flows.py` runs multi-step CLI flows on synthetic logbooks, verifying token refresh, concurrent-edit protection, artifact handoff, and read-only queries; each skill's `evals/evals.json` separately holds model decision scenarios. Passing CLI integration tests is not the same as passing model behavior evals; the latter also requires actually running the skills in a controlled environment and inspecting tool calls, file diffs, and answers — verbal plans alone are not scored.

The implementation lives in `src/logbook_cli/`: `commands/` handles Click parameters, `services/` handles use cases, `storage.py` guards writes, and `render.py` handles output. `models.py` defines semantic states and task annotations; `format.py` maps Markdown labels and markers. `document.py` parses and checks; `views.py` derives status and task-query views; `edit.py` performs minimal text edits. `bin/lb` use the existing checkout environment. For module execution use `uv run --locked python -m logbook_cli`. Install or refresh dependencies explicitly with `uv sync --locked --no-dev --project .lbkit`; reads never install or access the network.

Reproducible fixture preparation, non-clobbering prechecks, and event collection are described in the consuming repository's behavior-eval process.

## Feedback-era Write Extensions (0.2)

Successful logbook writes return `version_token` for the exact resulting bytes, including no-op writes. Dry-run returns the original current token, not a token for the uncommitted preview. This removes token-only reads between already-understood sequential writes; it does not make the sequence transactional or replace semantic rereading after conflicts or changed acceptance criteria.

`task rewrite LOG --stage STAGE --task OLD --text NEW --decision SOURCE --token TOKEN` changes only an unfinished agent task's first-line text, preserving its checkbox, position, children and repository ownership, and records the supplied decision in a status child. Human items, completed/skipped items, changed ownership, duplicate text and stale tokens are refused. The caller must verify authorization and evidence applicability; the CLI cannot authenticate the supplied decision.

For an explicitly authorized initial assignment, add `--assign-repo NAME` (without `@`) and include exactly `@NAME` in the new text. This permits assigning one repository only when the original unfinished agent task has none; it never transfers existing ownership or splits the task. Preview first with the same decision and token. The caller verifies the named repository is in the approved working directories and that the human decision authorizes this assignment; the flag and decision string cannot authenticate consent. All other rewrite protections remain in force.

`task split LOG --stage STAGE --task ORIGINAL --into FIRST --into SECOND --decision SOURCE --token TOKEN` replaces one unfinished agent package with at least two new, ordered, not-started tasks in the same stage, in one guarded write. Preview the entire transformation with `--dry-run`, inspect it, then write with that same token. The original task text, position and child content stay intact; its checkbox becomes `[-]` with a `not-applicable` resolution naming the decision and replacements. This retires the aggregate package from scheduling without claiming acceptance or cancellation of the underlying work. Each replacement gets a Source pointing to the original task's identity; it inherits no accepted state or artifact. Set any new criteria separately within the authorized scope.

Duplicate or existing replacement text, human/completed/skipped originals, human replacements and preflight gates are refused. If the original has repositories, replacements must collectively cover exactly those repositories and each must retain at least one; new repositories and loss of an existing repository are refused. An unassigned original may give each replacement at most one explicitly named repository. The caller verifies the human-approved scope, order, repositories and evidence applicability; `--decision` cannot authenticate consent. All candidate validation and CAS checks finish before any byte is written. Failed validation or stale tokens leave the original and replacements unchanged. Repeating a completed split is refused. Stage marker synchronization remains a separate current-token operation, as with `task add`.

`task resolve LOG --stage STAGE --task TEXT --as human-cancelled|not-applicable --decision SOURCE --note REASON --token TOKEN` adds a task-bound disposition to an already `[-]` item, including a human-owned item. It never changes the checkbox. The visible `处置：` JSON child includes `task` (SHA-256 of exact task text), `as`, `decision`, and `note`. Missing, conflicting, malformed or stale records do not close the task (`INVALID_RESOLUTION`). A changed task text invalidates the record; a mere `--as` option does not prove a human decision occurred.

Stages whose items are all accepted or explicitly dispositioned derive ✅. Context exposes each task's resolution; task queries retain the distinction between unresolved skips and dispositioned items. Summaries say “已收口（含取消/不适用项）” rather than claiming successful acceptance. All-skipped stages can close only with valid dispositions for every item. Existing unresolved skips retain their old non-pass behavior.

`link add LOG --stage STAGE --link '[label](target)' --token TOKEN` appends one Markdown link as a list item to the stage's `相关链接：` (`Related links:`) block, creating the block right before `待办：` when the stage has none; an identical existing line is refused. `link rewrite LOG --from PREFIX --to PREFIX --token TOKEN` replaces the prefix in every visible link target (code fences and comments untouched) and returns the `rewritten` list; it refuses the whole write when any rewritten target does not exist (`file://`, `~` and relative targets are resolved for this). That existence check covers only the links it rewrites: `check` still reports links outside the root as `LOCAL_LINK_UNVERIFIED` without probing them.

The low-level CLI remains a standard-library Markdown tool for inspection, migration and testing. Managed lb-* document workflows require mind-forge; CLI success does not establish mind-forge readiness, authorization or acceptance.

## Protected task details and offline observations

`task note --kind` also accepts Source/来源, Acceptance/验收 and Skills/技能. Values are single nonempty lines; new Skills are four-space-indented slash/backtick spans. Historical chain forms remain readable. Without `--replace-line N`, notes append and all Acceptance entries remain conjunctive. With that option, explicit Source/Acceptance/Skills replaces exactly the matching current task annotation line; a mismatch, stale token or ambiguous task is refused. Human items accept only the existing additive Status exception. Source/Acceptance append or replacement on `[x]` or `[-]` agent tasks requires an authorized reopening first; Skills correction establishes no new acceptance. Context exposes annotation kind/value/line and parsed skill names/diagnostics. Changed conditions invalidate affected returns/bindings.

Machine groups accept `- ` followed by a backticked explicit machine name, alongside legacy local/remote groups. Context preserves machine spelling and adds machine_name/group_kind. `skills usage --machine NAME` includes only that named group plus legacy local groups and this repository; without it named groups are not scanned. This selector grants no remote access and probes no remote filesystem.

```sh
bin/lb link verify log.md --line 18 --target 'https://sources.example.com/reference/12' --label 'Primary reference' --observed-at '2026-10-14T08:00:00+08:00' --observer sailor-a --basis 'Read with the host tool' --outcome verified --token TOKEN --dry-run --json
```

`link verify` registers an offline observation of one visible HTTP(S) link selected by current line, target and label. Overview, Source, Stage and protected human links are eligible; no task, Artifact or sidecar is required. Optional --bind-stage/--bind-task are paired for an outside-task result link; --result-identity records a supplied revision. Task-contained links bind automatically and cannot redirect to another task. Use --outcome verified/unavailable/revoked. The CLI records supplied facts; Sailor performs actual observations and Captain aligns the return. It never fetches, authenticates or certifies permanent availability.

Metadata is a compact reserved document-level `lb-link-verification` HTML comment, outside fences/task bodies/other comments. The semantic occurrence excludes checkbox state and physical line number; Source/Acceptance/Artifact snapshots bind task applicability. Changed target/label/context or bound values invalidate old observations without deleting history. Latest failure/revocation or equal-time conflicting observations remain unverified. Check suppresses only the eligible occurrence's LINK_UNVERIFIED; other occurrences and structural/local-link checks are preserved. Malformed records yield LINK_VERIFICATION_INVALID; context exposes observations/applicability. Arguments/time use exit 2, path errors 3 and stale/ambiguous/unsafe writes 4. Writes carry CAS and dry-run writes zero bytes.
