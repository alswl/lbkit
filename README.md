# lbkit

[English](README.md) | [中文](README.zh-CN.md)

Reusable Logbook coordination skills, Markdown contracts, and the `lb` CLI for human–agent collaborative delivery. Current version: see [VERSION](VERSION) (`bin/lb --version`).

## Overview

**lbkit** is a shared kit that gets mounted as a `.lbkit` Git submodule in a consuming repository. It provides the coordination skills, document contracts, and CLI that let a human owner, a coordinator agent, and executor agents deliver real projects through a plain Markdown **logbook** — the single source of scheduling truth.

- **Human owner** — owns goals, risk acceptance, and irreversible decisions
- **Coordinator agent** — maintains shared state, dependencies, and acceptance per logbook
- **Executor agents** — deliver bounded work packages with verifiable evidence

Authorization boundaries, evidence rules, and human checkpoints are contracts, not options. Plans don't authorize execution; agents never write to human-owned logbook items.

## Install

From a checkout of this repository, install it into another Git repository with one command:

```sh
./bin/lbkit install --repo /path/to/logbooks --source https://github.com/alswl/lbkit.git
```

`--source` may be omitted when this checkout has an `origin` remote. Add `--dry-run` to inspect the Git and link operations first.

The command adds the `.lbkit` submodule, links the CLI, skills, and shared docs, copies `lbkit-agents.template.yaml` when no `lbkit-agents.yaml` exists, generates an `AGENTS.md` stub when missing (placeholder collaboration rules to be filled in locally), creates a `CLAUDE.md -> AGENTS.md` link, and initializes a mind-forge repo when `minds.yaml` is absent (`minds.yaml` + `projects/`, produced via `mf init`; skipped with a hint when `mf` is not installed), then checks `bin/lb --help`. It refuses to replace existing files, and never commits or pushes either repository.

### Without a separate checkout

When no lbkit checkout exists on the machine, add the submodule to the target repository manually, then run install from inside `.lbkit`:

```sh
cd /path/to/logbooks
git submodule add https://github.com/alswl/lbkit.git .lbkit
./.lbkit/bin/lbkit install
```

Once it detects `.lbkit` is already a registered submodule, install skips the Git operations and only adds the links and template. `--repo` defaults to the current directory, so it can be omitted when run from the repository root.

The consuming repository owns its project logs, `AGENTS.md`, `lbkit-agents.yaml`, and the optional `lbkit-skills.json`; lbkit owns the shared implementation and instructions. Installed links:

```text
.agents/skills/lb-*  -> ../../.lbkit/skills/lb-*
.claude/skills/lb-*  -> ../../.lbkit/skills/lb-*
bin/lb               -> ../.lbkit/bin/lb
bin/lb-anywhere      -> ../.lbkit/bin/lb-anywhere
bin/lbkit            -> ../.lbkit/bin/lbkit
docs/<shared>.md     -> ../.lbkit/docs/<shared>.md
```

Only entry points are linked. The CLI implementation (`scripts/lb.py`, `src/logbook_cli`) stays inside the `.lbkit` submodule — `bin/lb` resolves it through its own path.

### Run from anywhere

`bin/lb` runs from the repository root. To invoke `lb` from any subdirectory of any consuming repository, link the wrapper once:

```sh
ln -s /path/to/repo/bin/lb-anywhere ~/.local/bin/lb
```

The wrapper walks up to the nearest `bin/lb`, switches to that repository root, and executes it — so the repository's pinned lbkit revision always stays in charge.

## Skills

| Skill | Role |
|---|---|
| [lb-init](skills/lb-init/SKILL.md) | Set up or refresh the `.lbkit` submodule and local entry points |
| [lb-scaffold](skills/lb-scaffold/SKILL.md) | Create a workflow instance logbook for a real project |
| [lb-plan](skills/lb-plan/SKILL.md) | Verify goals, draft todos for confirmation, design stages and work packages |
| [lb-preflight](skills/lb-preflight/SKILL.md) | Read-only preflight: route planning and step-by-step feasibility |
| [lb-push](skills/lb-push/SKILL.md) | Dispatch, resume, and monitor execution within granted authorization |
| [lb-update](skills/lb-update/SKILL.md) | Verify evidence, maintain records, close out human decisions |
| [lb-status](skills/lb-status/SKILL.md) | Observe logbooks and the control plane, report status briefs |

### Skills list (optional)

An optional `lbkit-skills.json` at the consuming repository root records skill chains by kind of work; lb-plan consults it when drafting a todo's `技能：` sub-line. Each entry has:

- `name`: the kind of work, e.g. "speckit implementation by task range"
- `scope`: where it applies and where it does not; lb-plan decides by scope, not by mechanically matching action prefixes
- `chain`: the skill chain, which may include skills that live only inside a business repository
- `actions`: common todo action prefixes, as hints only
- `companions`: skills used alongside the chain, each with a `when`
- `description`: preconditions, how to run it, limits, and sources

[schemas/lbkit-skills.schema.json](schemas/lbkit-skills.schema.json) describes the format; the file references it via a leading `"$schema"` key and records its format version in `"version"` (currently `0.1.0`). Without the file, lb-* behave as before. lb-update curates it from the logbooks' `技能：` sub-lines (`lb skills extract`) and the skills actually invoked in sessions (`lb skills usage`), preferring real usage, and writes entries with `lb skills add` after human confirmation.

## CLI

Run the CLI from the consuming repository root with `bin/lb`; it treats the current directory as the document root unless `--root` is supplied.

```sh
bin/lb check                 # validate one or all project logbooks
bin/lb context --json        # document state + version token for safe writes
bin/lb list                  # list project logbooks
bin/lb task list|next        # filter tasks / show next delivery task
bin/lb task add|update       # write tasks (requires --token from context)
bin/lb task note|artifact    # annotate tasks with notes or evidence
bin/lb sync                  # refresh stage emojis from task state
bin/lb skills [--action 开发]  # list lbkit-skills.json entries
bin/lb skills add            # append a kind of work (--name --scope --chain ...)
bin/lb skills extract        # 技能： sub-lines in logbooks not yet covered by the list
bin/lb skills usage          # skills actually invoked in sessions (the one read-only command outside --root)
```

All write commands require the SHA-256 `version_token` returned by `context --json`; writes are rejected on any concurrent change. See the [lb CLI contract](docs/lb-cli.md) for the full contract.

## Shared contracts (installed into consuming repositories)

Two documentation directories live in this repo: `docs/` holds the shared contracts distributed to consuming repositories (linked into their `docs/` on install), while `dev-docs/` holds lbkit's own development documentation and is **not** installed.

- [Lifecycle & skill entries](docs/lifecycle.md)
- [Coordination contracts](docs/coordination.md)
- [Logbook format](docs/logbook-format.md)
- [Evidence rules](docs/evidence.md)
- [Configuration & runtime adapters](docs/configuration.md)
- [`lb` CLI reference](docs/lb-cli.md)

## lbkit development

Documentation for developing lbkit itself — not installed into consuming repositories:

- [Development guide](dev-docs/development.md)
