# Document reading, writing, and checking

lb-plan, lb-push, lb-update, lb-status, and lb-preflight read this workflow before writing. lb-* entry points also use the CLI location and check workflow below when reading existing logbooks; pure reads never run write, index, or build steps. Choose documents.adapter per the [configuration contract](../../../docs/configuration.md); do not guess the storage tool from content subject matter.

## Shared steps

1. Resolve the actual logbook location and related records; user-specified paths win, and among multiple candidates none may be picked arbitrarily. Access only this round's approved scope. Before writing, always resolve locations and edits through the `readlink -f` real path — the repository root's CLAUDE.md and `.claude/skills/**` are often symlinks, and editing directly can be refused or hit the wrong file.
2. Before writing, re-read the target block and related decisions, preserving the user's concurrent edits and private feedback. Follow the [logbook format](../../../docs/logbook-format.md); never change task semantics or order through typesetting. The 「目标：」 lines of the overview and each stage, existing heading text, and numbering stay as-is; stage-status emoji may be synced per the rules.
3. Change only evidence-backed differences, using stable identities and links. Reuse existing locations for additional records; never auto-create a second task queue. The placement and wording of small fact fragments is left to the model, without per-fragment confirmation; preserve human prose and section structure. Large prose is written by the human and must not be split into multiple local rewrites.
4. Run the chosen adapter's checks proportional to the change's impact, confirming the target text, existing heading text, and numbering are unchanged before and after the write (stage-status emoji excepted), and state clearly what failed, was skipped, or did not apply. When check tooling is unavailable, keep a reviewable diff and report the verification gap; never auto-install tools or claim verification passed.

## CLI invocation in this repository

Structured reads, checks, and supported writes in this repository use [bin/lb](../../../bin/lb); commands and exit codes are in the [CLI reference](../../../docs/lb-cli.md). It is invoked by agents through terminal tools and does not run automatically from loading a skill. The coordinator may run this repository's document tool; it is not a cross-repository business or evidence-gathering script. The legacy entry point `python3 scripts/lb.py` still works.

Run the following commands from the logbooks root directory; if the current directory differs, use the absolute path of `bin/lb` and pass `--root <approved logbook root>` explicitly. The root is a path-protection boundary, not a source of authorization, and must not be widened to parent directories to bypass access denial.

```sh
bin/lb context '<logbook-relative-path>' --json
bin/lb check '<logbook-relative-path>' --json
```

- When the user has already specified the logbook, call `context` directly; use `list --json` only when the logbook is not yet located and discovering the host project is allowed, passing a non-default `documents.project_root` via `--projects-dir`. Never pick one of several candidates yourself. For plain Markdown a specified path need not be discovered first.
- Read the logbook source and the authorization basis alongside. `context` returns stages, task original text, line numbers, directories, and `version_token`; it does not contain full goals or authorization. `next_task` is only a parsed candidate — unknown states, skip records, or ambiguity must be verified against the source; never auto-skip items based on it. `bound_records` are body links only and cannot replace mind-forge metadata bindings.
- `check` is used for plan review, status verification, and post-write validation, targeting this round's logbook — not `--all` by default. On exit 1, read the problem details and distinguish structural errors from unverified links; it neither proves completion nor grants permission to fix or add tasks, and unrelated historical problems need not block the current task.

Writes to existing stage emoji, task status, and agent artifacts use the corresponding subcommands:

```sh
bin/lb sync '<logbook-relative-path>' --token '<version_token>' --dry-run --json
bin/lb task update '<logbook-relative-path>' --stage '<stage original text, without status emoji>' --task '<full task original text>' --status / --token '<version_token>' --dry-run --json
bin/lb task artifact '<logbook-relative-path>' --stage '<stage original text, without status emoji>' --task '<full task original text>' --artifact '产物：[report](report.md)' --token '<version_token>' --dry-run --json
```

When a human has already confirmed new items and their order, use `task add --stage <stage original text> --text <approved todo text> --token <version_token>`; for brief facts use `task note --stage <stage original text> --task <full task original text> --kind <产物|阻塞|状态|交接> --text <content> --token <version_token>`. Both dry-run first, then execute the write. Read-only inspection is available via `task list` (supports `--stage`, `--status`, `--human`) or `task next`; generate the human-scannable view with `todo` on first use. Execution approval for new todos still rests on the logbook and the human's confirmation; a command being available does not mean automatic authorization.

Check the dry-run diff first, then rerun the same approved write without `--dry-run` — no need to ask again for already-granted authorization. `/` is used only after confirmed receipt; `x` only after lb-update verifies the evidence. That the tool accepts other statuses does not mean the skill is authorized to cancel, skip, or reopen tasks. Strict read-only and plan review never call write subcommands, including their dry-run.

Locate tasks by stage and full task original text from `context`; line numbers are for reporting only. Text may contain backticks or `$()` — pass it as literal argv safely, never assembled into a shell string that would expand. After every successful write, re-fetch `context` and the token before the next `artifact`, `sync`, or status change; write commands do not return new tokens, and multi-step updates are not transactions. Before retrying, verify which steps already succeeded and which artifact lines exist, avoiding duplicate appends.

When resuming a multi-step update, read back the operations that already succeeded and complete only the remaining steps that still apply. Resuming `artifact → sync` does not authorize adding `task update --status x`; entering completion-state updates requires current-candidate acceptance evidence plus authorization that includes acceptance. Do not re-append an existing artifact; a file existing is not acceptance.

On exit 2, correct arguments per the actual CLI interface; on exit 3, verify path and authorization; on exit 4, re-read the source and context and re-judge whether the item, evidence, and edit still apply. When candidate or acceptance semantics changed, return to the acceptance workflow to re-check evidence first — never retry the checkbox by merely swapping token and task text. When a task has vanished or is ambiguous, stop that write and state the gap; never bypass refusal with line numbers, regexes, or whole-page overwrites. When real side effects are unknown, read the file back first.

`sync` changes only determinable stage H2 emoji and the page-top machine-readable status summary already owned by the CLI; it does not touch human comments or ordinary fact fragments, and it does not replace acceptance. New logbooks and local body edits the script does not support still follow the shared write protections; confirmed new todos, task status, artifacts, and brief task notes prefer the protected subcommands. Never rewrite whole pages because the CLI lacks support. When the script is missing, Python is unavailable, or the format cannot be parsed, keep query and review of the readable source and report the check gap; supported status writes must not silently switch channels to bypass protection. External plain-Markdown backends are not forced to install this repository's scripts; maintain them per their existing document adaptation and authorization.

## documents.adapter=markdown

Maintain the given plain Markdown logbook directly. Do not create bound prompts/thinking when none exist; write decision rationale into the existing corresponding stage or a user-designated record.

After writing, check Markdown structure, local links, checklist item order, and semantic fit with this change. Do not run mf, do not require minds.yaml, and do not build or publish a site. Read-only mode skips the post-write steps.

## documents.adapter=mind-forge

Read the document mapping guide from the host's `lbkit-agents.yaml` key `documents.mind_forge_guide`, and together with the mf-cli skill in the current environment, locate the canonical article, its uniquely bound prompt, and the corresponding thinking. If the guide is missing and cannot be verified read-only in the host repository, consult the human; metadata is authoritative, project_root is only a discovery scope — never hard-code project names or file names.

Preserve user content: persistent writing constraints go in the prompt, sources/decisions/evidence indexes go in thinking, and the main logbook keeps the results.

When splitting an article is approved, first confirm the migration mapping per lb-plan; sync the unique prompt bindings, scope constraints, and corresponding thinking between old and new articles. Historical evidence may stay in the original ledger and be referenced by the new one; never duplicate it into a second task list. After creating files manually, rehearse first, then update the project-level article index; read back the bindings and titles from article show and check relative links. Never treat the index's default draft/published status as task acceptance, and never treat an auto-derived file-name title as a human-edited body title.

Choose checks proportional to the change's impact: for emoji and small fact fragments, at minimum verify the diff, related items, and protected fields; when terminology, links, or article structure change, run the applicable term check, article check, index, or build rehearsal. No need to rerun the full chain for every status-fragment change; specific commands follow current CLI capabilities — never guess parameters.

Changes to root instructions, skills, or ordinary docs are not project articles; do not run mf for them. Real builds, publishes, commits, pushes, and external work-item changes require their own authorization; adapter choice authorizes none of these side effects.
