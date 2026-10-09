# lbkit Development Guide

This document covers development and maintenance of the lbkit repository itself and is **not distributed** to consuming repositories on install. For shared contracts aimed at consuming repositories, see `docs/`; for skills, see `skills/`.

## Directory Structure

```text
skills/        # lb-* skills, for consuming repositories; linked as their .agents/skills/lb-* on install
docs/          # shared contract documents, for consuming repositories; linked as their docs/<name>.md on install
dev-docs/      # lbkit's own docs (this directory), not installed
bin/           # the lb, lb-anywhere, and lbkit installers
src/           # the logbook_cli Python package
scripts/       # the lb.py entry script
tests/         # unittest tests
```

## Running Tests

Only the Python 3 standard library is required:

```sh
python3 -m unittest discover tests
```

## Checklist for Changing Shared Contracts

Contract files (`docs/`) and skills (`skills/`) are installed into consuming repositories, so when changing them:

1. **Relative links must also resolve inside the consuming repository.** Skills live at the installed `.agents/skills/lb-X/`, symlinked to `.lbkit/skills/lb-X/`; contracts live in the consumer's `docs/`, pointing to `.lbkit/docs/`. Within a skill, reference contracts as `../../docs/...` in SKILL.md (`../../../docs/...` from the references subdirectory); within a contract, reference skills as `../skills/...`. You can write paths according to lbkit's internal layout — inside a consuming repository they resolve through the symlinks to the same file under `.lbkit/`.
2. **Update `manifest()` in `bin/lbkit`** if you add a new top-level directory or file that must be installed.
3. **Run the full test suite**; for installer-related changes also run `python3 -m unittest tests.test_lbkit_install`.
4. **The consuming repository owns** its project logbook, `AGENTS.md`, `lbkit-agents.yaml`, and optional `lbkit-skills.json`; do not inject new obligations into it through shared contracts without documenting them here.

## Versioning and Evolution

lbkit uses semantic versioning; the current version is recorded in the root `VERSION` file (first release 0.1.0) and printed by `bin/lb --version`. The version covers three kinds of objects: lbkit as a whole (shared contracts, CLI, and installer), each lb-* skill (the `version` field in SKILL.md frontmatter), and the config formats owned by consuming repositories (`version` in `lbkit-agents.yaml`, `"version"` in `lbkit-skills.json`). During 0.x, breaking changes bump the minor version and compatible changes bump the patch version; whenever you change a skill or a format, bump its version in sync, and when a config format changes, also update the list of versions its readers support. Each consuming repository still pins one exact revision via the submodule pointer and chooses its own upgrade timing — updating the submodule pointer is the upgrade. Therefore:

- Keep contract changes backward compatible where possible (adding fields beats changing semantics).
- Note the change points of breaking changes in the corresponding contract document so consumers can evaluate whether to upgrade.
- CLI write operations carry a `version_token` (SHA-256 CAS) to prevent concurrent-write conflicts; the matching between logbook files and parsing code is guaranteed by the pinned revision.
