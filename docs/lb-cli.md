# `lb`: the guarded lightweight Logbook CLI

`bin/lb` uses only the Python 3 standard library, built for structured reading of this repo's Markdown conventions and minimal-scope edits. It is not a scheduler: it never accepts delivery, dispatches work, presumes authorization, or reorders checklist items, and it never touches the network.

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

# Generate/refresh docs/TODO.md beside the logbook (a slow-paced human view: 🚨 interventions, 👱 todos, next item, in progress)
bin/lb todo projects/example/docs/logbook.md
bin/lb todo projects/example/docs/logbook.md --dry-run   # look, don't write
bin/lb todo projects/example/docs/logbook.md --json     # machine-readable structure

# Sync delivery-stage H2 emoji and the adopted top status line; inspect a dry run first
bin/lb sync projects/example/docs/logbook.md --token 0123... --dry-run

# Pass the version_token returned by context unchanged into precise write operations
bin/lb task update projects/example/docs/logbook.md \
  --stage 'Stage 01 实现' --task '开发：实现 CLI。 @logbooks 🤖️' \
  --status / --token 0123... --dry-run
bin/lb task artifact projects/example/docs/logbook.md \
  --stage 'Stage 01 实现' --task '开发：实现 CLI。 @logbooks 🤖️' \
  --artifact '产物：[CLI](../scripts/lb.py)' --token 0123...

# Append a todo to a confirmed stage, or place it before an existing todo in that stage
bin/lb task add projects/example/docs/logbook.md \
  --stage 'Stage 01 实现' --text '测试：验证 CLI。 @logbooks' --token 0123... --dry-run
bin/lb task add projects/example/docs/logbook.md \
  --stage 'Stage 01 实现' --text '测试：验证 CLI。 @logbooks' --before-line 42 --token 0123...

# Append one short fact under an agent todo; kind is one of 产物, 阻塞, 状态, 交接
bin/lb task note projects/example/docs/logbook.md \
  --stage 'Stage 01 实现' --task '开发：实现 CLI。 @logbooks 🤖️' \
  --kind 阻塞 --text '🚨 请人类负责人完成登录；登录后恢复。' --token 0123... --dry-run

# Human todos only, or just the next item
bin/lb task list projects/example/docs/logbook.md --human --json
bin/lb task list --status in-progress --json
bin/lb task next projects/example/docs/logbook.md --json

# Optional repository-root lbkit-skills.json (JSON Schema: .lbkit/schemas/lbkit-skills.schema.json, referenced by the file's leading "$schema" key, with "version" as the format version, currently only 0.1.0): registers skill chains by kind of work; fields name, scope (usage range), chain, actions (action-prefix hints), companions (companion skills: skill + when), description
bin/lb skills --json
bin/lb skills --action 开发 --json
bin/lb skills add --name 'speckit 功能实现' --scope '适用：…；不适用：…' --chain speckit-implement --action 开发 --companion 'comment-prune=实现完成、提交前' --dry-run
bin/lb skills usage --since 2026-10-01   # skills actually invoked in Claude Code and Codex sessions; the only command reading outside --root (~/.claude, ~/.codex), counting only sessions whose working directory falls in a logbook-registered directory or this repo
bin/lb skills extract --json   # 「技能：」 sub-lines not covered by any entry (skill chain or companion skill), listed verbatim with the todo's original text, completion status, and the work package pointing back to it
```

`--root` defaults to the current directory and can confine every path to a synthetic repository or worktree:

```sh
bin/lb --root /tmp/fixture context projects/demo/docs/log.md --json
```

`check`'s `DUPLICATE_TASK_TEXT` flags unclosed same-text tasks within one Stage (historical duplicates that are all checked no longer warn) — a preview that later write commands targeting the task's original text will be rejected as ambiguous. `local_target` runs expanduser ownership judgment on links starting with `~`; those outside the root still count as LOCAL_LINK_UNVERIFIED.

The "next item" in `context`, `state`, and `todo` is computed only from unfinished todos in `Stage NN` delivery stages; global checkbox lists in an old logbook's Overview take no part in scheduling.
`task list` and `task next` use the same delivery-stage scope; `task list` filters by stage, status, and human ownership, and lists todos across all discovered logbooks when the logbook path is omitted.

Discovery defaults to `projects/*/docs/*.md` inside the root; `list`, `check --all`, and `task list` accept `--projects-dir` to pass in the host-configured `documents.project_root`, and recognize candidates with the heuristic "exactly one visible H1, plus an H2 stage or a todo"; this excludes `thinking/` and `prompts/` but is not a semantic classifier for arbitrary articles. The `projects`, project, and `docs` directories all get containment checks before traversal; directories pointing outside the root or otherwise anomalous are not traversed. Headings, todos, and links inside code fences and HTML comments do not participate in parsing; a trailing HTML comment hides only the comment itself, so a task before the comment keeps its full original text and updatable identity. If a multiline comment's closing line is followed by structural text, `COMMENT_STRUCTURE_AMBIGUOUS` is reported rather than guessing the parse. A fence closes only with a fence of the same character, sufficient length, and nothing but whitespace at end of line. `context.stages[].tasks` gives each item's original text, status, line number, repository marker, and human marker. `bound_records` lists only places in the body that explicitly link to `thinking/` or `prompts/` — bindings are never guessed from same-named files.

## Write and Concurrency Protection

Every write operation (including `sync`) must supply the SHA-256 `version_token` returned by `context --json`. Any single-byte file change, or a stage and task original text that cannot be uniquely matched, refuses the write with exit code 4; an invalid status value is a parameter error with exit code 2. Tasks are located by the stage heading (minus the status emoji) plus the full original task text — never by line number. `task update` refuses to change the checkboxes of `👱` or `人工验证：` human items; `task artifact` and `task note` refuse to write sub-lines onto human-owned items. `task add` creates only not-started items and rejects same-text todos in the same stage; `--before-line` must point at the first line of an existing todo in that stage. Before using `task add`, an agent still needs the human's explicit confirmation of the new items and their order. `--dry-run` writes nothing and prints a reviewable unified diff (the JSON `diff` field).

All write commands re-parse the candidate text before writing and reject newly introduced deterministic `check` issues (such as missing in-repo links). Pre-existing issues do not block unrelated local updates; transient stage emoji, explicit `[-]`, unfetched external links, and unverified local links outside the repository count as permitted notices. The `issues_introduced` field of the JSON write result is an empty list when admission passes. `task artifact` and `task note` place new sub-lines after the existing indented sub-items; appending a duplicate is refused when an identical sub-line already exists. When `task note` text starts with `🚨 ` and a `--kind` is given, the marker stays at the very front of the sub-item body.

Before writing, the tool re-checks root containment and the source file's bytes after fsyncing the temp file and before `os.replace`, then performs the same-directory atomic replacement. This narrows the clobber window of ordinary concurrent editing but is not a CAS/lock guarantee against arbitrary editors or malicious processes; on conflict, still re-read context after the refused write.

Paths resolve symlinks on both read and write, and targets must still lie inside `--root`. The exception is read-only `skills usage`: it reads session records from `~/.claude/projects` and `~/.codex/sessions`, reporting only sessions whose working directory falls in a logbook-registered directory or this repo. Edits preserve UTF-8, the original CRLF/LF style, and all untouched bytes; `sync` only changes the H2 emoji of delivery stages whose status is determinable — empty stages, stages containing `[-]`, and unknown statuses are never judged complete. `[-]` is reported by `check` as an explicit not-applicable/skip record, not as not-started or an approval signal.

## Checks, Status, and Limits

`check` reports issues in the format `路径:行号:代码:说明`, with `--json` returning the equivalent structure. Exit codes: 0 no deterministic issues (there may still be `LINK_UNVERIFIED` notices), 1 deterministic issues found, 2 command parameter error, 3 path/read refusal, 4 concurrency or write-protection refusal. HTTP(S) links are only reported as `LINK_UNVERIFIED` — the network is never touched; local links are checked only for existence within the root. The tool parses no arbitrary YAML and validates nothing about external files, remote links, or mind-forge metadata.

External URLs (such as Forgejo PR links) report `LINK_UNVERIFIED` by design — a deterministic notice, not a structural error; a PR link is the run instance's identity notation, so keep it and never downgrade the link to plain text just to clear the notice.

## The 🔮 preflight gate

When any todo's or indented sub-item's checkbox text contains `🔮` (a pending-discussion blocker produced by lb-preflight and written in after human confirmation), the whole logbook is considered halted:

- `context --json` returns `preflight_blockers` (each with `line`, `text`, `indent`, `stage`) and `preflight_clear: false`; each task's `preflight` boolean marks whether that line is a blocker.
- `check` reports `PREFLIGHT_BLOCKER` for every 🔮 checkbox line (a deterministic status record, same class as `[-]`'s `SKIPPED_EXPLICIT`, contributing to exit code 1).
- `sync`, `task update`, `task artifact`, `task add`, and `task note` all refuse to write with exit code 4, with the error naming the line; the CLI offers no bypass flag — the only way out is a human rewriting or removing the 🔮 in the logbook text, then re-fetching `context`.

The tool only detects markers and does not verify a 🔮's provenance; write and adjudication semantics are in [Logbook Format](logbook-format.md) and the lb-preflight SKILL.

## Top Status Line and Structured State

Manage status emoji through this script first; do not hand-edit H2 emoji or the machine-readable status segment. `state --json` gives a structured snapshot: overall counts (delivery stages done/in_flight/not_started), `summary` (the derived machine-readable string), `next_task`, the 🔮 gate, and the `owned` attribution of every `> 状态：` line.

The top `> 状态：` line splits at the first `——`: the first half is the machine-readable segment, which `sync` rewrites to the derived string when it starts with 🛫/🚧/✅ — `状态：<emoji> <首个未验收交付阶段> · [🔮 待讨论 N 项 · ]下一项：<待办原文>` (or `状态：✅ 全部交付阶段已完成` when everything is done) — reported as `summary_updated` / `summary_kept_human`; the second half, the human commentary, is preserved verbatim. Narrative lines that do not start with an emoji, or that lack the divider, are treated as human prose and never touched, and no status line is auto-created for logbooks without one.

Running tests:

```sh
python3 -m unittest discover -s tests -v
```

## TODO.md Human View

The `todo` subcommand organizes the logbook into a `TODO.md` beside it, built for human scanning: 🚨 unplanned items needing the human owner (taken from todo first lines or sub-lines containing 🚨, verbatim with the exact action and clearing condition), 👱 unfinished human todos, the next item in document order, and items in progress. When there are no `[ ]` or `[/]` items but a `[-]` remains, it shows "skipped items pending disposal" instead of claiming full completion. The file header carries a machine-maintenance comment and the regeneration command; hand edits get overwritten. Non-dry-run writes from `sync` and `task update/artifact/add/note` automatically re-parse and refresh an existing `TODO.md` (it is not auto-created when absent — start with the `todo` command). The file is a derived view: it participates in no parsing, checks, or acceptance judgments.

## Skill Integration and Evaluation

lb-* entries call the CLI at their respective steps; the shared flow is in [document adapters](../skills/lb-update/references/document-adapters.md#本仓-cli-调用): plan reads and checks, push marks in progress after taking a task, status queries and syncs authorized emoji, update updates status and artifacts after evidence acceptance; preflight is a read-only analysis entry, with blocker write-back done by the skill within the logbook write boundaries — never through CLI write subcommands. The script neither runs these skills itself nor checks task authorization or evidence sufficiency.

`tests/test_lb_skill_flows.py` runs multi-step CLI flows on synthetic logbooks, verifying token refresh, concurrent-edit protection, artifact handoff, and read-only queries; each skill's `evals/evals.json` separately holds model decision scenarios. Passing CLI integration tests is not the same as passing model behavior evals; the latter also requires actually running the skills in a controlled environment and inspecting tool calls, file diffs, and answers — verbal plans alone are not scored.

The implementation lives in `src/logbook_cli/`: `cli.py` handles argparse, writes, and output; `document.py` handles parsing and checks; `views.py` handles the status and TODO derived views; `edit.py` handles task text editing and pre-write candidate checks. `bin/lb` is the quick entry, `python3 scripts/lb.py` remains for compatibility, and `PYTHONPATH=src python3 -m logbook_cli` also works. `scripts/` keeps only directly runnable entries and eval tooling. The implementation stays on the Python standard library, and eval fixtures carry the full package.

Reproducible fixture preparation, non-clobbering prechecks, and event collection are described in the consuming repository's behavior-eval process.
