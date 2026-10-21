# Review design: document model and CLI layers

Status: implemented under human authorization; repository checks passed. Human review remains a human decision. This records the design associated with the 2026-10-11 Fude comments; validation below is historical, not a claim about the current candidate.

## Diagnosed problems

- Skill extraction called the document parser but rescanned tasks with another regex, omitting `* [ ]` tasks accepted by the main parser.
- Mixed backticked and bare skill names silently lost the second name; English Skills labels were not recognized.
- Localized labels and emoji combined storage, rendering and business-state decisions. Stage state returned emoji that other services compared as semantic state.
- CLI registration, handlers, writes and output were concentrated in one module. Changing frameworks alone would not remove that coupling.
- The initial baseline had 84 passing tests; temporary fixtures reproduced the extraction defects without modifying consumers.

## Model and representation

Keep Markdown as the editable source of truth, without a parallel task list. Define TaskState, StageStatus, Owner, Task, TaskAnnotation and SkillChain with stable English enum values and retained source ranges/text. Extract skills from parsed task annotations, not a second task regex. Tasks without action prefixes remain tasks even when excluded from registry candidates.

Parse skill chains explicitly: bare/backticked names, slash prefixes, order, separators and trailing explanations. Ambiguous values retain their source and return diagnostics rather than silently dropping items. Legacy work-package matching by early lines, localized headings and quoted prefixes remains heuristic, not identity or acceptance proof; explicit binding needs a separate compatibility design.

Centralize bilingual field mappings such as `技能` / `Skills` and `处置` / `Resolution`. Parse ownership and gate markers at the same boundary. Stage semantic states map to emoji for rendering; a settled list can include cancellation rather than success. Preserve source labels, unrelated text, line endings and human suffixes on writeback. Keep existing JSON fields, state characters and derived_emoji compatible. Label mappings alone do not establish general multilingual support; mixed labels and default rendering need explicit tests.

## CLI migration

The human requested a mainstream framework and reference to the Python CLI guidance in github.com/alswl/guides. Inspection found Python server and Go CLI guides, but no separate Python CLI standard. Applicable principles were explicit domain types, layers, uv/uv.lock/uv_build, thin command modules, services and clear output streams/exit codes. HTTP, database and Go-specific mechanisms were not imported.

Click was selected and approved for command groups, shared options and independent registration. It was a project decision, not a framework mandated by those guides.

- Entrypoints own registration, help/version, argument adaptation and error mapping.
- Logbook/task/skill command modules reuse root, JSON, token and dry-run options.
- Services compose use cases; domain code handles state, ownership, disposition and skill candidates; storage retains path checks, CAS and atomic replacement.
- Presentation emits data to stdout and errors to stderr. Preserve aliases, root at each command level, positional arguments after `--`, exit codes 1/2/3/4 and JSON/dry-run contracts.
- Declare and lock dependencies; support reproducible consumer installation and both bin/lb and python -m logbook_cli. Help/version never install dependencies implicitly. Update installation and standard-library-only claims with the actual dependency model.

## Validation sequence

Add regressions for the reported failures, mixed chains, fences/comments, unknown labels, actionless tasks and ambiguity. Compare equivalent English/Chinese semantic snapshots and minimal writes, including CRLF, human suffixes, cancellation and stale tokens. Unify parsing before isolating label mappings; migrate command groups without mixing in unrelated semantic changes. Test missing dependencies, fresh consumer installation, non-repository cwd, help/version and output streams. Finish with full tests, links and isolated installation; never resolve human review automatically.

## Historical implementation and evidence

models.py, format.py and messages.py separate semantic models, bilingual encoding and task presentation. Skill extraction walks parsed annotations; invalid chains return source plus diagnostics. Click modules live in commands/, use cases in services/, writes in storage.py and presentation in render.py. No arguments shows help; aliases, root options and error codes remain supported.

The installer creates the locked runtime in the consumer's .lbkit/.venv; launchers only use an existing environment and report repair commands when dependencies are missing. The bootstrap installer keeps standard-library argparse; the main CLI uses Click. The human corrected an unauthorized 0.3.0 bump and selected 0.2.0-dev / 0.2.0.dev0 at that time. Configuration schema stayed unchanged; release decisions remain human-owned.

Historical checks used Python 3.14.8:

1. New regressions initially produced five failures and two missing-model/result errors.
2. Full tests passed: 96, compared with the initial 84, covering CAS, paths, ownership, models, syntax, CLI and installation.
3. Ruff and basic mypy checks passed; this did not establish strict typing of all historical JSON records.
4. All 163 links across 34 Markdown files and diff whitespace checks passed.
5. An isolated consumer installed a real uv runtime, initialized through a simulated mf and exposed --version outside its cwd. A dependency-free Python reported an error without installing anything.
6. Source/wheel builds and offline wheel installation in a separate environment passed help/version and English read/token-guarded write checks.

No real consumer/submodule pointer was updated and no publication, commit or push occurred. These checks did not revalidate live mind-forge, Herdr or provider integrations. Supported languages use explicit mappings, legacy package association remains heuristic, and Python 3.11 remains the declared minimum.
