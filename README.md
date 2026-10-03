# lbkit

[English](README.md) | [中文](README.zh-CN.md)

Reusable Logbook coordination skills, Markdown contracts, and the `lb` CLI for human–agent collaborative delivery.

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

The command adds the `.lbkit` submodule, links the CLI, skills, and shared docs, copies `SKILL-PARAMS.template.yaml` when no `SKILL-PARAMS.yaml` exists, then checks `bin/lb --help`. It refuses to replace existing files, and never commits or pushes either repository.

The consuming repository owns its project logs, `AGENTS.md`, `.agents/lb.yaml`, and `SKILL-PARAMS.yaml`; lbkit owns the shared implementation and instructions. Installed links:

```text
.agents/skills/lb-*  -> ../../.lbkit/skills/lb-*
bin/lb               -> ../.lbkit/bin/lb
bin/lb-anywhere      -> ../.lbkit/bin/lb-anywhere
bin/lbkit            -> ../.lbkit/bin/lbkit
docs/<shared>.md     -> ../.lbkit/contracts/<shared>.md
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
```

All write commands require the SHA-256 `version_token` returned by `context --json`; writes are rejected on any concurrent change. See the [lb CLI contract](contracts/lb-cli.md) for the full contract.

## Shared contracts (installed into consuming repositories)

- [Lifecycle & skill entries](contracts/lifecycle.md)
- [Coordination contracts](contracts/coordination.md)
- [Logbook format](contracts/logbook-format.md)
- [Evidence rules](contracts/evidence.md)
- [Configuration & runtime adapters](contracts/configuration.md)
- [Skill parameters](contracts/skill-params.md)
- [`lb` CLI reference](contracts/lb-cli.md)

## lbkit development

Documentation for developing lbkit itself — not installed into consuming repositories:

- [Development guide](dev-docs/development.md)
