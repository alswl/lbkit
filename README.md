# lbkit


Reusable Logbook coordination skills, Markdown contracts, and the `lb` CLI for human–agent collaborative delivery. Current version: see [VERSION](VERSION) (`bin/lb --version`).

## Overview

**lbkit** is a shared kit that gets mounted as a `.lbkit` Git submodule in a consuming repository. It provides the coordination skills, document contracts, and CLI that let a human owner, a coordinator agent, and executor agents deliver real projects through a plain Markdown **logbook** — the single source of scheduling truth.

- **Admiral (human)** — owns goals, risk acceptance, and irreversible decisions
- **Captain (coordination agent)** — maintains goals/routes, dependencies, dispatch and progress; personally executes scoped difficult work through takeover
- **Sailors (execution agents)** — perform business work, testing, review and acceptance, returning current results and outcomes

Authorization boundaries, applicable executor results, and human checkpoints are contracts, not options. Plans don't authorize execution; agents cannot complete human-owned items. They can record when human review starts.

## Install

Follow the [installation and upgrade guide](docs/guide/install.md). mind-forge is required.

## Skills

| Skill | Role |
|---|---|
| [lb-init](skills/lb-init/SKILL.md) | Set up or refresh the `.lbkit` submodule and local entry points |
| [lb-scaffold](skills/lb-scaffold/SKILL.md) | Create a workflow instance logbook for a real project |
| [lb-plan](skills/lb-plan/SKILL.md) | Verify goals, draft todos for confirmation, design stages and work packages |
| [lb-preflight](skills/lb-preflight/SKILL.md) | Read-only preflight: route planning and step-by-step feasibility |
| [lb-push](skills/lb-push/SKILL.md) | Dispatch, resume, and monitor execution within granted authorization |
| [lb-takeover](skills/lb-takeover/SKILL.md) | Captain personally resolves a scoped difficult problem |
| [lb-handback](skills/lb-handback/SKILL.md) | Return execution to Sailor with verified receipt |
| [lb-update](skills/lb-update/SKILL.md) | Refresh verified progress, or reread human edits without writing |
| [lb-status](skills/lb-status/SKILL.md) | Observe logbooks and the control plane, report status briefs |

### Configuration and recipes

`lbkit.yaml` holds settings and launchable agents; `lbkit-skills.yaml` holds the
repository's work-type skill recipes, which may name skills from any source. Use
`lb config show/check/resolve`, `lb config agent`, and `lb config recipe`.
Registry writes change one object with an expected file version and a preview.
See the [configuration contract](docs/installable/configuration.md) for the model,
lifecycle and examples. Agent bindings remain runtime data;
actual skill usage belongs in Thinking.

## CLI

Run the CLI from the consuming repository root with `bin/lb`; it treats the current directory as the document root unless `--root` is supplied.

```sh
bin/lb log check LOG             # validate one or all project logbooks
bin/lb log context LOG --json    # document state + version token for safe writes
bin/lb log list                  # list project logbooks
bin/lb task list|next        # filter tasks / show next delivery task
bin/lb task add|update       # write tasks (requires --expect-version from context)
bin/lb task note|artifact    # annotate tasks with notes or evidence
bin/lb log sync                  # refresh stage emojis from task state
bin/lb config recipe list --status available
bin/lb config resolve --json
bin/lb config agent list
bin/lb skill extract        # 技能： sub-lines in logbooks not yet covered by the list
bin/lb skill history          # skills actually invoked in sessions (the one read-only command outside --root)
```

All write commands require the SHA-256 `version_token` returned by `log context --json`; writes are rejected on any concurrent change. See the [lb CLI contract](docs/installable/lb-cli.md) for the full contract.

## Shared contracts (installed into consuming repositories)

Start at the [documentation index](docs/README.md) for user guides, contributor documentation and reference navigation. Only `docs/installable/` is distributed to consuming repositories, under their existing `docs/` paths.

- [Lifecycle & skill entries](docs/installable/lifecycle.md)
- [Coordination contracts](docs/installable/coordination.md)
- [Logbook format](docs/installable/logbook-format.md)
- [Configuration & runtime adapters](docs/installable/configuration.md)
- [`lb` CLI reference](docs/installable/lb-cli.md)

## lbkit development

Documentation for developing lbkit itself — not installed into consuming repositories:

- [Development guide](docs/dev/development.md)

The [core concepts](docs/guide/concept.md) explain Logbook → Stage → task, three roles and machine/session scheduling. Human-readable status stays in the briefing or existing CLI queries; writes create no TODO companion. Business originals/checks follow host rules, with no mandatory evidence/source index.
