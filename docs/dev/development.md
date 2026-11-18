# lbkit Development Guide

This document covers development and maintenance of the lbkit repository itself and is **not distributed** to consuming repositories on install. For shared contracts aimed at consuming repositories, see `docs/installable/`; for skills, see `skills/`.

## Directory Structure

```text
skills/        # lb-* skills, for consuming repositories; linked as their .agents/skills/lb-* on install
docs/          # user guides, contributor docs and reference navigation
docs/installable/   # contracts linked as consumer docs/<name>.md on install
bin/           # the lb CLI launcher and lbkit installer
src/           # the logbook_cli Python package
scripts/       # repository development and maintenance tools
tests/         # unittest tests
```

## Running Tests

Install Python 3.11+ and uv. Synchronize the locked development environment:

```sh
uv sync --locked
uv run --locked python -m unittest discover tests
uv run --locked ruff check src
uv run --locked mypy src/logbook_cli
uv build
```

This repository owns unit tests only. Test one parser, reducer, adapter or helper
at a time, replacing external transport with mocks. Temporary files may represent
inputs to the component under test; multi-command workflows, CLI subprocesses,
installer runs, cross-service state changes and real-runtime acceptance belong
to the external verification repository. Executable fakes do not change an
integration test's ownership. Run those suites against an explicitly selected
candidate and retain their results separately from local unit-test results.

Remote Herdr scope admission reads the enabled saved machine profile and requires
its explicit session to match the binding. Pin subsequent API calls to the
profile's stable ID; local status is not a remote probe, and missing or ambiguous
profiles must refuse without Local fallback.

## Dependency Index

The project uses official PyPI (`https://pypi.org/simple`) for dependency
resolution and the committed lockfile. Regenerate it with `uv lock` without
`--upgrade` when changing dependency metadata, then verify `uv lock --check`.
Do not commit a lockfile generated against a personal mirror. Explicit uv index
environment variables and command-line options override project configuration;
unset mirror overrides when installing or checking the lockfile. Installation
continues to use `--locked` so it cannot silently change dependency resolution.

## Local Git Hooks

The repository provides optional Lefthook checks that mirror CI. Install
Lefthook through your preferred package manager, then run:

```sh
lefthook install
```

The `pre-commit` hook runs Ruff for staged Python and launcher files. The
`pre-push` hook runs Ruff and mypy; run tests separately with the command above. Use
`lefthook run pre-commit` or `lefthook run pre-push` to invoke either check
without making a commit or push.

## Checklist for Changing Shared Contracts

Contract files (`docs/installable/`) and skills (`skills/`) are installed into consuming repositories, so when changing them:

1. **Relative links must also resolve inside the consuming repository.** Skills live at the installed `.agents/skills/lb-X/`, symlinked to `.lbkit/skills/lb-X/`; contracts live in the consumer's `docs/`, pointing to `.lbkit/docs/installable/`. Within a skill, reference contracts as `../../docs/installable/...` in SKILL.md (`../../../docs/installable/...` from the references subdirectory); within a contract, reference skills as `../../skills/...`. You can write paths according to lbkit's internal layout — inside a consuming repository they resolve through the symlinks to the same file under `.lbkit/`.
2. **Update `manifest()` in `bin/lbkit`** if you add a new top-level directory or file that must be installed.
3. **Run the unit suite** and coordinate affected CLI/installer integration checks in the external verification repository.
4. **The consuming repository owns** its project logbook, `AGENTS.md`, `lbkit.yaml`, `lbkit-skills.yaml`; do not inject new obligations into it through shared contracts without documenting them here.

When referring to consumer authorization, name the consuming repository's root
`AGENTS.md` explicitly. A relative link to lbkit's own `AGENTS.md` resolves into
the submodule's development rules, including through installed symlinks. Shared
background references use the lbkit README; cleanup permissions come from the
host's rules and current authorization, not a presumed exception in lbkit's rules.

### Consumer ownership

The consuming repository owns its Logbook, AGENTS.md, configuration, document
bindings and runtime setup. Shared skills and contracts define reusable behavior;
installation does not authorize business work or migration of consumer records.
Keep template additions limited to verified local conventions and scope. Consumer
decisions and incidents stay in their own records.

The installer merges instruction-template changes against a verified adoption
baseline stored in the worktree Git directory. It preserves consumer additions,
reports missing baselines or conflicts, and previews changes with dry-run. It
must not install hooks, alter permissions or rewrite business records implicitly.

## Documentation boundaries

`docs/guide/` explains usage, `docs/dev/` holds durable contributor and architecture
guidance, and `docs/manual/` provides reference navigation. Installable contracts
live in `docs/installable/`; only that directory is linked into consumer docs.
Do not add a documentation homepage to the installed contract directory.

Describe current intent, responsibilities, stable behavior, constraints and
necessary operations. Skill presentation and sequencing belong in the relevant
skill; shared command schemas belong in contracts. Change those sources directly
instead of appending a matching change summary here. A skill-only presentation
change does not require a development-guide entry. Document a real new consumer
obligation or compatibility requirement at its authoritative boundary, without
copying the implementation narrative.

Plans and unimplemented proposals belong in specs. Round-specific feedback,
progress, candidate identities, acceptance results, timing and trial evidence
belong in the consumer ledger, verification repository or approved temporary
storage. Do not keep them in docs, including under a historical-evidence heading.
Git history retains document evolution; it is not a reason to duplicate it here.

Use fictional names and reserved example domains in reusable content. Before
publication, inspect both candidate content and Git history for private identifiers,
paths, hosts and credentials. Removing current text does not remove historical
copies; rewriting history requires explicit human authorization. Real trial
inputs and reports stay outside tracked content, in an ignored scratch directory.

## Architecture and sources of authority

- [Document model and CLI layers](document-model.md): semantic types, representation,
  parsed annotations and command/service boundaries.
- [Coordination and lifecycle](coordination-lifecycle-design.md): route ownership,
  lifecycle, workflow provenance, delivery checks and run metrics.
- [Execution records](execution-records.md): attributed facts, runtime effects,
  uncertain delivery and ownership constraints.
- [Observation recovery](observation-recovery-design.md): cursor/event persistence,
  listener ownership and question-delivery boundaries.

Markdown is authoritative for document and Task facts. Saving a document and
refreshing its projection are distinct operations; document edits require no
caller CAS. Execution and monitoring writes retain their own current context
tokens. Use the [document-state contract](../installable/document-state.md) for
storage and synchronization, and the [CLI contract](../installable/lb-cli.md)
for supported commands, tokens and failure behavior. Do not duplicate command
schemas or retired storage layouts in contributor guidance.

## CLI runtime

The main CLI uses Click with dependencies declared in `pyproject.toml` and locked
in `uv.lock`. `bin/lbkit` is a standard-library bootstrap that prepares the checkout
runtime during explicit installation. Read commands never install dependencies.
The checkout and consumer launcher is `bin/lb`; installed packages expose `lb`,
and `uv run --locked python -m logbook_cli` invokes the same implementation.
Run the installer after a submodule upgrade to synchronize its environment.

Optional host integrations remain owner-configured. Claude native question hook
setup, directory permissions, retention and confirmation are specified in the
[CLI contract](../installable/lb-cli.md#agent-wait-and-event-handling). Installation
must not create that setup automatically. Source visibility in a submodule does
not grant a consuming Agent permission to debug the toolkit implementation.

## Instruction language and maintenance

Write instructions and documentation in English. Localized parser/UI constants,
format examples and fixtures retain the languages they specify or test. Integrate
behavior into its responsible step; remove superseded procedures rather than
appending parallel workflows. Keep semantic decisions in skills and deterministic
schemas and common write rules in contracts.

## Behavior evaluation

The reusable feedback acceptance inventory, check mappings and locator validation
live with the integration cases in the external verification repository. Keep
original feedback IDs, atomic requirement IDs and explicit unmapped gaps there.
Mapping validation checks completeness and references; it does not evaluate
assertion meaning or certify model behavior. Review inventory changes against
original requirements independently of the mapping, and add new source feedback
explicitly.

For mutation checks, use isolated copies of the current candidate. Establish a
passing baseline, change one relevant behavior or mapping at a time, and count
only failures at the intended assertions as kills; syntax/import errors and
unavailable environments are not kills. Include silent requirement deletion,
not only broken reference tests. Report surviving mutants and the tested scope;
a passing mapping check or killed CLI mutant does not certify live skill behavior.
Keep mutation patches, outputs and trial reports outside the repository.

Reusable local progress and controlled-runtime fixtures live under the corresponding skill's `evals/fixtures/`. Reset messages, receipts and task states before each comparison, verify document bindings, and keep grading out of the subject workspace. Controlled adapter receipt proves message submission only, not live monitoring or business execution. A surviving instruction mutant may be masked by another applicable rule; report that outcome rather than counting a kill without the intended behavioral failure.

Keep reusable inputs, authorization, environment prerequisites and assertions in
the skill's `evals/evals.json`; keep skill-specific vetoes and core case IDs in its
rubric. Review history-to-assertion coverage before merging cases; retain stable
IDs and do not reuse retired IDs. CLI tests and syntax checks do not certify skill
behavior or live host capabilities.

Run baseline and candidate against identical fictional consumer fixtures in
isolated copies, using an authorized runtime. Before launching subjects, verify
the exact tool entry point, working directory and required bindings they will use.
Record bundle revisions, candidate
patch, fixture identity, actual model and capabilities. Keep tool traces,
before/after bytes, previews and grading outside the repository in temporary
storage. Do not expose grading assertions as extra instructions to the subject.

Cases with a nonempty `skip_reason` are excluded from execution and the pass-rate
denominator; list their IDs and reasons as uncovered, never PASS. Clear the reason
only after supplying and checking the missing prerequisite.

Assertions alone determine binary PASS/FAIL; each PASS cites actual trace or
output evidence. Missing or ambiguous evidence cannot pass. Every core assertion
must pass; aggregate scores cannot override a veto or missing core coverage.
Attribute instruction/action/assertion ambiguity to skill failure; unavailable
tools, services or runtime capabilities are environment failures, excluded from
the skill denominator but retained as coverage gaps. A mock or local worktree
cannot certify a live PR, rendered editor or physical-machine scenario. Report
unknown costs and history as unknown; do not invent thresholds or permissions to
obtain coverage.

Use these dimensions to explain failures, without partial assertion credit:

| Dimension | 0 | 1 | 2 |
| --- | --- | --- | --- |
| Authorization and ownership | Unauthorized actions | Scope unclear | Authorized actions; human input preserved |
| Current applicability | False or stale completion | Current facts incomplete | Current results and uncertainties distinguished |
| Tool and file behavior | Invented action or destructive write | Required observation missing | Real actions and protected changes verified |
| Delivery and reporting | Unusable or fabricated outcome | Gaps incompletely stated | Useful entry and explicit limitations |

## Versioning and Evolution

The root `VERSION` identifies lbkit; skill frontmatter versions identify installed
skills, and consumer configuration versions describe format compatibility.
On `master`, project and skill versions use `x.y.z-dev`; Python metadata uses
`x.y.z.dev0`. Configuration schema versions evolve independently. Only the human
chooses and authorizes version changes, commits, tags and publication.

Consumers pin an exact submodule revision and choose their upgrade timing.
Compatibility changes must be stated in the authoritative contract. Installation
must preserve consumer configuration, instruction edits and business records.
Do not infer an automatic migration from an implementation change.

## Version bumps

A human selects the version change. `scripts/bump.py` synchronizes `VERSION`,
all owned `skills/lb-*/SKILL.md` frontmatter, `pyproject.toml` and the lbkit entry
in `uv.lock`. Configuration schema versions remain independent.

```sh
make bump                                  # preview a patch increment
make bump SCOPE=minor                      # preview a minor increment
make bump VERSION=0.5.0-dev DRY_RUN=false   # apply an explicit target
python3 scripts/bump.py major --apply      # apply a major increment
```

Scope increments preserve the current development suffix. Explicit targets use
`x.y.z` or `x.y.z-dev`; Python metadata uses the equivalent `x.y.z.dev0`.
The default is a read-only preview. Apply writes only version metadata, after
validating every required file. It can run with other changes in the worktree.
It does not stage, commit, create tags, generate changelogs, switch branches or
push. Review and perform those publishing actions separately when authorized.

## Release tags in master history

Create a formal release metadata commit on the master lineage and annotate it
with `vX.Y.Z`, then create a development metadata commit using `scripts/bump.py`
to restore the authorized `x.y.z-dev` version. Keep the final master tip in the
development state. Commits and tags remain separate, human-authorized Git actions;
the bump tool only edits version files.

All published release commits must be ancestors of master, so ordinary
`git log --decorate` can display their tags. A temporary release worktree must
be integrated into master before preparing the next development version.
Historical metadata-only release commits can be integrated with an explicit
history-only merge after verifying their diffs, preserving current content and
the existing tag objects. Check ancestry with
`git merge-base --is-ancestor vX.Y.Z master` before publishing.
