---
name: lb-init
version: 0.5.0-dev
description: "Install or refresh lbkit, or migrate and maintain lbkit.yaml settings and agents and lbkit-skills.yaml recipes. Configuration-only work uses the registry CLI without installation or runtime execution. Creating a workflow instance belongs to lb-scaffold."
---

Read the [document state and CLI failure recovery contract](../../docs/installable/document-state.md).
If lb is unavailable or crashes, notify the user and take over safe authorized work;
report pending writes and verification gaps instead of silently stopping or bypassing CAS.


# Connect lbkit to a Logbook repository

The consuming repository owns project logs, its `AGENTS.md`, `lbkit.yaml` (settings and agents) and `lbkit-skills.yaml` (skill recipes). lbkit owns the shared skill implementations, contracts, templates, and CLI. Read the consuming repository's instructions and Git state before changing it. Preserve existing project content and local configuration.

## User-facing line guidance

Installation and configuration replies normally need no Logbook line. If a migration question concerns a specific existing Logbook item, apply the [locator guidance](../../docs/installable/coordination.md#human-facing-logbook-locators): name the file, item and verified `L50` position; do not create a Logbook just to supply a locator.

## Configuration only

For an existing host's configuration rewrite or registry change, read the
[configuration contract](../../docs/installable/configuration.md) and use
`bin/lb config`, `bin/lb config agent` or `bin/lb config recipe`. This mode does
not install tools, refresh links, require a document backend, or start agents.
Preview the authorized single-object change with the current token, apply it and
read back the result. A conflict requires rereading before retry; never change
other objects or lifecycle states merely to bypass a reference refusal.
For older files, rewrite them into the current format per the
[configuration contract](../../docs/installable/configuration.md#older-files), show the
diff, run `bin/lb config check`, and remove the old files only with human agreement.
Resolve effective values and sources without executing the selected launcher or skills.
Report changed fields and remaining work. Use the installation sections only when installation is requested.

## New connection

1. Verify mind-forge is installed (`mf version`) and the target can maintain a mind repository. It is required, not a best-effort optional integration. If missing, use the available mf-cli installation guidance to prepare or perform an authorized installation; never silently skip it or report lbkit ready. Confirm the lbkit remote and intended revision with the user or existing repository records. A submodule needs a committed revision; when commits are prohibited, prepare files and report that registration must wait.
2. Run `bin/lbkit install --repo <target-repository> --source <lbkit-git-url> --dry-run`, inspect conflicts, then run the same command without `--dry-run`. The command adds `.lbkit` as a submodule and installs relative links for the CLI, `lb-*` Skills, and shared docs. It refuses to overwrite existing files or same-name local skills; review those before migration.
3. Read the collaboration parameters in the [configuration contract](../../docs/installable/configuration.md#collaboration-parameters). Rewrite older configuration files as described above. Use `lb config show/check/resolve`, `lb config agent` and `lb config recipe` for discovery and atomic registry changes with the current file token and a dry run. Fill host-owned settings with known values; ask the user for required values that cannot be verified. Keep `lbkit.yaml` and `lbkit-skills.yaml` local and set settings.documents.adapter=mind-forge, provide the host mapping guide, and configure runtime adapters from actual capabilities and approved model choices. Put short references to the installed shared contracts and skill paths in the consuming `AGENTS.md`. Do not replace its owner, authorization boundaries, or project instructions with generic text.
4. Run the applicable shared tests. Report the submodule revision, installed links, local configuration left to the consuming repository, and any missing capability.

## Existing connection

Inspect local changes and compare the old and new lbkit contracts before updating the submodule revision. Refresh only broken or newly required links. Verify mf remains installed even when minds.yaml exists. Migrate legacy markdown configuration to mind-forge explicitly, preserving the consumer's content and establishing Prompt/Thinking bindings according to existing host-owned records. Re-run the CLI and tests, and report any migration needed in local rules or configuration.

Never create or amend commits when the user has forbidden commits. A stash can hold a prepared migration, but it cannot replace the commit required for a usable submodule pointer.
