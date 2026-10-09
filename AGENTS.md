# AGENTS.md

This file contains the development conventions for the lbkit repository itself and is not distributed to consuming repositories on install; for the collaboration template aimed at consuming repositories, see [AGENTS.template.md](AGENTS.template.md).

## Project

lbkit provides cross-repository reusable `lb-*` collaboration skills, Markdown contracts, and the `lb` CLI, installed into consuming repositories as a Git submodule; it is implemented in pure Python 3 standard library with no third-party dependencies. For background aimed at consumers, see [README.md](README.md).

## Common Commands

- Full test run: `python3 -m unittest discover tests`
- Installer unit tests: `python3 -m unittest tests.test_lbkit_install`
- CLI self-check: `./bin/lb --help`, `./bin/lb --version`

## Structure

- `skills/lb-*/` — the `lb-*` skills; linked as consumer `.agents/skills/lb-*` on install
- `docs/` — shared contract documents; linked as consumer `docs/<name>.md` on install
- `dev-docs/` — lbkit's own development docs, not installed
- `bin/` — the `lb`, `lb-anywhere`, and `lbkit` installers
- `src/logbook_cli/`, `scripts/lb.py` — CLI implementation
- `tests/` — unittest tests

## Hard Rules

- Never commit or push automatically: leave Git changes in the working tree or staging area; commit and push only when a human explicitly instructs it.
- Relative links inside `docs/` and `skills/` must still resolve in a consuming repository after symlink resolution: SKILL.md uses `../../docs/...`, the references subdirectory uses `../../../docs/...`, and contracts referencing skills use `../skills/...`.
- When adding a new top-level installed directory or file, update `manifest()` in `bin/lbkit` accordingly.
- Bump versions whenever you change a skill or a config format: the overall version lives in `VERSION`, each skill's version in its SKILL.md frontmatter; during 0.x, breaking changes bump the minor version.
- CLI write commands must carry the `version_token` (SHA-256 CAS) returned by `context --json` to prevent concurrent-write conflicts; do not bypass this.
- The consuming repository owns its logbook, `AGENTS.md`, and `lbkit-agents.yaml`; do not inject new obligations into consumers through shared contracts without documenting them in dev-docs.

## References

- [dev-docs/development.md](dev-docs/development.md) — required reading before changing contracts, skills, or the installer: link rules, install manifest, version evolution.
- [docs/lb-cli.md](docs/lb-cli.md) — when changing CLI behavior: command contracts and the `version_token` write rules.
