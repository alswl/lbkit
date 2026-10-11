# AGENTS.md

This file contains the development conventions for the lbkit repository itself and is not distributed to consuming repositories on install; for the collaboration template aimed at consuming repositories, see [AGENTS.template.md](AGENTS.template.md).

## Project

lbkit provides cross-repository reusable `lb-*` collaboration skills, Markdown contracts, and the `lb` CLI, installed into consuming repositories as a Git submodule; it uses Python 3.11+ and Click, with dependencies locked by uv. For background aimed at consumers, see [README.md](README.md).

## Common Commands

- Full test run: `uv run --locked python -m unittest discover tests`
- Installer unit tests: `uv run --locked python -m unittest tests.test_lbkit_install`
- CLI self-check: `./bin/lb --help`, `./bin/lb --version`

## Structure

- `skills/lb-*/` — the `lb-*` skills; linked as consumer `.agents/skills/lb-*` on install
- `docs/installable/` — shared contract documents; linked as consumer `docs/<name>.md` on install
- `docs/` — lbkit documentation; only `docs/installable/` is installed
- `bin/` — the `lb`, `lb-anywhere`, and `lbkit` installers
- `src/logbook_cli/`, `scripts/lb.py` — CLI implementation
- `tests/` — unittest tests

## Hard Rules

- Never commit or push automatically: leave Git changes in the working tree or staging area; commit and push only when a human explicitly instructs it.
- Keep non-public product names, internal project or consuming-repository identifiers, personal site addresses, and private environment details out of repository content, including documentation, skills, evals, tests, examples, and commit messages. Use generic fictional names and reserved example domains; retain real names only when the owner has confirmed they may be public. Before preparing changes for publication, check both current content and Git history for leaks; deleting or replacing current text does not remove historical copies. Rewrite history only with explicit human authorization.
- `docs/dev/` (and repo docs generally) holds long-lived documentation only. Do not record per-round feedback processing, acceptance status, or trial-run evidence in repo docs: pointed conclusions land in contracts/skills/evals/tests, the consumer's ledger and its git history own the per-item record, and trial artifacts stay in ephemeral directories.
- Relative links inside `docs/installable/` and `skills/` must still resolve in a consuming repository after symlink resolution: SKILL.md uses `../../docs/installable/...`, the references subdirectory uses `../../../docs/installable/...`, and contracts referencing skills use `../../skills/...`.
- When adding a new top-level installed directory or file, update `manifest()` in `bin/lbkit` accordingly.
- On `master`, project and skill versions use `x.y.z-dev`; Python package metadata uses the equivalent PEP 440 `x.y.z.dev0`. Config schema versions describe compatibility and are independent of release suffixes. Only the human may decide and authorize version upgrades. Do not automatically bump `VERSION`, package versions, skill frontmatter versions, or config format versions when changing implementation. Report any release or compatibility implications and wait for an explicit version instruction; synchronize dependent metadata only with that instruction.
- CLI write commands must carry the `version_token` (SHA-256 CAS) returned by `context --json` to prevent concurrent-write conflicts; do not bypass this.
- The consuming repository owns its logbook, `AGENTS.md`, and `lbkit-agents.yaml`; do not inject new obligations into consumers through shared contracts without documenting them in docs/dev.

## References

- [docs/dev/development.md](docs/dev/development.md) — required reading before changing contracts, skills, or the installer: link rules, install manifest, version evolution.
- [docs/installable/lb-cli.md](docs/installable/lb-cli.md) — when changing CLI behavior: command contracts and the `version_token` write rules.
