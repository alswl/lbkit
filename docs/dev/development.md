# lbkit Development Guide

This document covers development and maintenance of the lbkit repository itself and is **not distributed** to consuming repositories on install. For shared contracts aimed at consuming repositories, see `docs/installable/`; for skills, see `skills/`.

## Directory Structure

```text
skills/        # lb-* skills, for consuming repositories; linked as their .agents/skills/lb-* on install
docs/          # user guides, contributor docs and reference navigation
docs/installable/   # contracts linked as consumer docs/<name>.md on install
bin/           # the lb, lb-anywhere, and lbkit installers
src/           # the logbook_cli Python package
scripts/       # the lb.py entry script
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

## Behavior evaluation

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
