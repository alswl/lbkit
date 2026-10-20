# lbkit Development Guide

This document covers development and maintenance of the lbkit repository itself and is **not distributed** to consuming repositories on install. For shared contracts aimed at consuming repositories, see `docs/installable/`; for skills, see `skills/`.

## Directory Structure

```text
skills/        # lb-* skills, for consuming repositories; linked as their .agents/skills/lb-* on install
docs/          # user guides, contributor docs and reference navigation
docs/installable/   # contracts linked as consumer docs/<name>.md on install
bin/           # the lb, lb-anywhere, and lbkit installers
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
3. **Run the full test suite**; for installer-related changes also run `uv run --locked python -m unittest tests.test_lbkit_install`.
4. **The consuming repository owns** its project logbook, `AGENTS.md`, `lbkit-agents.yaml`, and optional `lbkit-skills.json`; do not inject new obligations into it through shared contracts without documenting them here.

When referring to consumer authorization, name the consuming repository's root
`AGENTS.md` explicitly. A relative link to lbkit's own `AGENTS.md` resolves into
the submodule's development rules, including through installed symlinks. Shared
background references use the lbkit README; cleanup permissions come from the
host's rules and current authorization, not a presumed exception in lbkit's rules.

## Versioning and Evolution

lbkit uses semantic versioning; the current version is recorded in the root `VERSION` file (first release 0.1.0) and printed by `bin/lb --version`. The version covers three kinds of objects: lbkit as a whole (shared contracts, CLI, and installer), each lb-* skill (the `version` field in SKILL.md frontmatter), and the config formats owned by consuming repositories (`version` in `lbkit-agents.yaml`, `"version"` in `lbkit-skills.json`). On `master`, project and skill versions use `x.y.z-dev`; Python package metadata uses the equivalent PEP 440 `x.y.z.dev0`. Configuration schema versions remain independent compatibility identifiers. Only the human decides and authorizes version upgrades. Agents must not automatically bump package, skill, or configuration versions. Report compatibility implications separately; update versions and dependent metadata only on explicit instruction. Semantic versioning informs the human release decision. Each consuming repository still pins one exact revision via the submodule pointer and chooses its own upgrade timing — updating the submodule pointer is the upgrade. Therefore:

- Keep contract changes backward compatible where possible (adding fields beats changing semantics).
- Note the change points of breaking changes in the corresponding contract document so consumers can evaluate whether to upgrade.
- CLI write operations carry a `version_token` (SHA-256 CAS) to prevent concurrent-write conflicts; the matching between logbook files and parsing code is guaranteed by the pinned revision.

## 0.2 Consumer Migration

Managed logbooks use the declared document adapter; consumers own their configuration migration. Business record retention follows the host contract.
Research and other non-software results must remain first-class
behavioral test cases. Do not infer that a passing CLI suite proves skill behavior
or live runtime/provider compatibility.

## Documentation Layout

Use `docs/guide/` for product usage and `docs/dev/` for contributions and long-lived development guidance. `docs/manual/` provides reference navigation.

Keep installable contract bodies in `docs/installable/`. The installer links only those Markdown files into consumer `docs/` directories. Do not put a documentation homepage in `docs/installable/`, because it would become an installed contract.

After moving a contract, update skill references and the installer mapping. Test both a new installation and recognized legacy links. Consumer documents and unrelated symlinks must remain untouched.

## CLI and document model migration

The CLI uses Click and uv. The installer remains a small standard-library bootstrap so it can create the CLI environment before importing Click. `pyproject.toml` and `uv.lock` stay in the submodule; `lbkit install` runs `uv sync --locked --no-dev --project .lbkit`. The launchers use the existing `.lbkit/.venv`, preserve the caller's working directory, and never download dependencies on a read command. Rerun the installer after a submodule upgrade.

`commands/` adapts Click parameters, `services/` implements use cases, `storage.py` owns guarded writes, and `render.py` owns CLI output. `models.py` defines semantic task/stage states and annotations. `format.py` owns Markdown labels and marker mappings. `document.py` parses once, and skill extraction consumes its task annotations.

The runtime dependency change requires consumer environment setup; its release version is for the human to decide. Existing command names, JSON fields, error codes, tokens and dry-run behavior remain compatible. English labels and text stage markers are optional additions. The format is explicitly bilingual, not arbitrary-language inference.

The existing unittest suite remains the regression baseline. Ruff and basic mypy checks cover the source package; strict typing of every historical JSON record is not yet complete.

## Human edits and progress refresh

`lb-update` keeps two intents in one entry. A human edit notification defaults to
read-only alignment with the current logbook. It does not create mind-forge
bindings, write Thinking, sync markers or begin execution. A reliable prior
version is required to claim a difference; otherwise report current understanding.
A request to refresh progress permits reading already-authorized available records
and writing supported facts. Mixed requests reread first and re-evaluate evidence
against the edited criteria. The existing format/progress/close modes apply only
after an authorized write is selected. This adds no consumer configuration or
new approval requirement; project and skill versions remain unchanged.

## Logbook coordination migration

The coordination revision uses three roles: Admiral supplies goals and authorization, Captain maintains the route and coordinates assignments, and Sailor performs business work including testing, review and acceptance. Independent checks, when needed, are Sailor tasks. A current result and applicable acceptance return support progress; a runtime exit or a bare completion claim does not. Status-only requests authorize no new business execution.

The revision intentionally removes the `lb todo` companion-view command and automatic TODO.md refresh, and retires the shared evidence.md/source-index rule model. It does not delete consumer-owned TODO files, business sources, human instructions or historical records. Installer migration must remove only exactly recognized installer-owned retired symlinks; copied files and unrelated links remain owned by consumers. Consumers decide their submodule revision and local instruction changes. No automatic version or config upgrade accompanies this work.

Skills reconcile Sailor returns rather than requiring a framework acceptance archive. The host determines business record storage and delivery layout. Requested run statistics use the existing bound Thinking. Skill evaluation follows the behavior evaluation rules below.

Delivery follows the host plan and explicit Admiral ruling. A PR-required gate retains PR/head/accessibility checks; branch-only review uses the branch/ref and candidate identity with a usable entry. Uncommitted changes are not branch contents. This adds no mandatory PR or permission to commit, push or merge.

Delivery scope is defined in the [coordination contract](../installable/coordination.md#human-deliveryreadiness--us4). Its inventory, binding and final-link checks clarify existing host-owned delivery rules; they add no consumer configuration, mandatory archive or cleanup authorization. Document identity comes from explicit paths or host metadata rather than naming conventions.

## Design and direct dialogue migration

Consumers adopting this revision gain a design-readiness obligation before ordinary lb-push: Captain personally develops specs with Admiral in authorized project repositories and links the current design and confirmation to the route. Reuse existing applicable specs and confirmations; no required Spec Kit installation, fixed spec path, additional CLI state, config field or automatic version bump is introduced. Host design workflows and write permissions still apply. Captain's spec authorship is an explicit planning responsibility; implementation, POCs and acceptance remain Sailor work. Requests to create or draft the supplied Logbook route authorize saving proposed result-oriented unfinished agent-task wording within that scope, including in an existing draft, before final design confirmation. Spec/Thinking-only proposals leave the Logbook unchanged and authorize no task writes or previews. Older narrow editing limits do not override a newer planning request; confirmed scope/order, human tasks and execution gates remain protected. This clarifies planning authorization rather than adding a new approval or CLI write bypass. Existing annotation refinements use the matching `task note --replace-line` operation and current token; first-line task rewrites and direct body edits are not substitutes. Bound Thinking body edits are distinct: resolve/check identity with mind-forge and use the host writer or authorized local Markdown edit, while preserving bindings and content. The missing dedicated Thinking-write subcommand alone creates no new adapter prerequisite.

Preflight may inspect unfinished design. A real POC requires an explicit todo, affected-route reorganization and renewed Admiral discussion, then bounded execution authorization; completion cannot silently release ordinary implementation. Design reading, spec writing and execution permissions remain distinct across repositories. Specs own design prose; Logbook owns scheduling; Thinking/Sources retain decisions or references under host rules.

Direct Admiral–Sailor dialogue requires Captain's permission and a verified interaction window for the owning Sailor. Captain recovers attributable content, decisions and open points into the applicable existing records before affected work resumes or the entry closes. This is a scoped interaction capability, not permission to start extra executors or a requirement for a new transcript archive. Consumers own adoption in their AGENTS and runtime conventions; the installer must not overwrite these. Existing Admiral rulings remain authoritative and are not subject to a second approval by Captain.

## Behavior evaluation

The optional `task split` command adds atomic replacement of an explicitly
authorized unfinished agent package. It retains the original identity and
evidence using the existing skipped/not-applicable disposition, and creates
ordered not-started tasks with source provenance. It adds no document schema,
configuration or consumer adoption requirement. Repository coverage and human
protections are enforced by the CLI; authorization and evidence applicability
remain the caller's responsibility. Existing task commands keep their behavior.

The reusable feedback acceptance inventory lives in
`tests/fixtures/feedback_requirements.json`; its separate check mapping lives in
`tests/fixtures/feedback_coverage.json`. Keep original feedback IDs, atomic
requirement IDs and explicit unmapped gaps. `tests/test_feedback_coverage.py`
checks inventory completeness, assertion references/polarity and CLI test
locators; it does not evaluate assertion meaning or certify model behavior.
Review inventory changes against original requirements independently of the
mapping. New source feedback must be added to that inventory explicitly.

For mutation checks, use isolated copies of the current candidate. Establish a
passing baseline, change one relevant behavior or mapping at a time, and count
only failures at the intended assertions as kills; syntax/import errors and
unavailable environments are not kills. Include silent requirement deletion,
not only broken reference tests. Report surviving mutants and the tested scope;
a passing mapping check or killed CLI mutant does not certify live skill behavior.
Keep mutation patches, outputs and trial reports outside the repository.

Feedback-derived refinements retain host-owned records: current status replaces stale summaries locally while dated evidence stays in existing Thinking; operation returns distinguish effective configuration/results from intent and unverified recovery; planning compares workflows, definitions and shared review allowances across the confirmed route. These clarify existing acceptance and authorization duties, without requiring a new archive or configuration. The optional `task rewrite --assign-repo` adds initial assignment of an unassigned unfinished agent task under an explicit decision; default rewrites still preserve ownership. Existing owners, human items, CAS and previews remain protected. This is an additive CLI capability; no version or schema change is made without human instruction.

Actionable return gaps belong in the existing task and its owning return: a configuration correction requests the evidence applicable to the actual tool (pipeline configuration/graph/results or local target/digest/exit/readback), rather than universally requiring pipeline fields; an update-only delivery note names the owner and missing inventory/binding checks without dispatching. Recovery records retain the exact supported scope and evidence pointer even when the task completes. These clarify existing return alignment; they introduce no new host configuration, archive, approval or business execution permission.

Feedback expresses a reported symptom and a proposed solution, not an automatic new consumer obligation. Validate both against the task's intended result and host ownership. Pair success-dependent operations with diagnosis-only tasks, pipeline evidence with local tools that have no graph, and explicitly required independent reviews with routes that need only self-checks. Formatting and renderer preferences are host-specific unless already part of the shared format contract. Review limits count agreed independent submissions, not all tests or environments. These clarifications add no new configuration fields, universal review gates or execution permission.

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

## CLI entry points

`bin/lb` is the checkout and consumer launcher; it loads `src/logbook_cli/`
and uses the existing checkout environment. Installed Python packages expose
`lb` through `pyproject.toml`; `uv run --locked python -m logbook_cli` invokes
the same implementation. `scripts/` contains repository maintenance tools only.
The former `python scripts/lb.py` compatibility entry is removed; consumers
using it must switch to `bin/lb` on submodule upgrade. The installer requires
only the supported launchers and package files, and adds no consumer obligations.

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

## Scoped Captain execution migration

`lb-push` now selects scoped `lb-takeover` automatically for difficult work and
`lb-handoff` when its exit condition is met. This relaxes the former unconditional
Sailor-only execution boundary. Consumers adopting it should reconcile explicit
local prohibitions in their own AGENTS/runtime instructions; shared skills never
override them. Existing authorization covers mode changes, not new business scope.
Captain direct checks retain attribution and do not replace required independent
review. Ownership checkpoints use existing Thinking/host records; no new consumer
configuration, CLI state or mandatory archive is introduced. New skills are picked
up by the installer's existing directory enumeration. Re-run the installer after
upgrading the submodule. No version or schema bump is made without human instruction.

The takeover display uses `状态：🧑‍✈️ Captain 接手` under the task, with host
field-language preservation. `task note --kind Status/状态 --replace-line` now
replaces a matching agent-task Status line under the existing CAS/preview rules.
It preserves comment suffixes and line endings, rejects stale/mismatched writes
and still forbids human-task replacement. This additive CLI capability avoids
competing current statuses; it introduces no parsed emoji/state or schema change.
