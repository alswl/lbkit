---
name: lb-init
version: 0.3.0-dev
description: "Set up or refresh a Logbook repository's .lbkit submodule and thin local entry points for shared lb skills, docs, and CLI. Use for repository scaffolding, not for creating a workflow run logbook (lb-scaffold)."
---

# Connect lbkit to a Logbook repository

The consuming repository owns project logs, its `AGENTS.md`, `lbkit-agents.yaml`, and the optional `lbkit-skills.json` skills list; install does not create the list. lbkit owns the shared skill implementations, contracts, templates, and CLI. Read the consuming repository's instructions and Git state before changing it. Preserve existing project content and local configuration.

## New connection

1. Verify mind-forge is installed (`mf version`) and the target can maintain a mind repository. It is required, not a best-effort optional integration. If missing, use the available mf-cli installation guidance to prepare or perform an authorized installation; never silently skip it or report lbkit ready. Confirm the lbkit remote and intended revision with the user or existing repository records. A submodule needs a committed revision; when commits are prohibited, prepare files and report that registration must wait.
2. Run `bin/lbkit install --repo <target-repository> --source <lbkit-git-url> --dry-run`, inspect conflicts, then run the same command without `--dry-run`. The command adds `.lbkit` as a submodule and installs relative links for the CLI, `lb-*` Skills, and shared docs. It refuses to overwrite existing files or same-name local skills; review those before migration.
3. Read the collaboration parameters in the [configuration contract](../../docs/installable/configuration.md#collaboration-parameters). Fill the consuming repository's `lbkit-agents.yaml` with known values; ask the user for required values that cannot be verified. Keep `lbkit-agents.yaml` local and set documents.adapter=mind-forge, provide the host mapping guide, and configure runtime adapters from actual capabilities and approved model choices. Put short references to the installed shared contracts and skill paths in the consuming `AGENTS.md`. Do not replace its owner, authorization boundaries, or project instructions with generic text.
4. Run the applicable shared tests. Report the submodule revision, installed links, local configuration left to the consuming repository, and any missing capability.

## Existing connection

Inspect local changes and compare the old and new lbkit contracts before updating the submodule revision. Refresh only broken or newly required links. Verify mf remains installed even when minds.yaml exists. Migrate legacy markdown configuration to mind-forge explicitly, preserving the consumer's content and establishing Prompt/Thinking bindings according to existing host-owned records. Re-run the CLI and tests, and report any migration needed in local rules or configuration.

Never create or amend commits when the user has forbidden commits. A stash can hold a prepared migration, but it cannot replace the commit required for a usable submodule pointer.
