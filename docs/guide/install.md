# Install lbkit

From a checkout of this repository, install it into another Git repository with one command:

```sh
./bin/lbkit install --repo /path/to/logbooks --source https://github.com/alswl/lbkit.git
```

`--source` may be omitted when this checkout has an `origin` remote. Add `--dry-run` to inspect the Git and link operations first.

The installer requires Python 3.11+, uv, Git, and a runnable mind-forge CLI (`mf`). Install it using the [mind-forge installation instructions](https://github.com/alswl/mind-forge).

The installer performs these operations:

1. Check required tools and path conflicts.
2. Initialize `minds.yaml` and `projects/` with `mf init` when needed.
3. Add or initialize the `.lbkit` submodule.
4. Create `.lbkit/.venv` from `uv.lock`, then link the CLI, skills, and shared contracts.
5. Create missing configuration and instruction templates.
6. Check `bin/lb --help`.

If mf is missing or initialization fails, the installer stops before it writes shared links. The installer preserves existing files. It does not commit or push.

After installation, configure `lbkit.yaml` for mind-forge and the actual runtime, and register the repository's skill recipes in `lbkit-skills.yaml` when useful. Fill the generated `AGENTS.md` with the repository's rules. See the [configuration reference](../installable/configuration.md).

### Without a separate checkout

When no lbkit checkout exists on the machine, add the submodule to the target repository manually, then run install from inside `.lbkit`:

```sh
cd /path/to/logbooks
git submodule add https://github.com/alswl/lbkit.git .lbkit
./.lbkit/bin/lbkit install
```

Once it detects `.lbkit` is already a registered submodule, install skips the Git operations and refreshes the locked CLI environment, links and templates. `--repo` defaults to the current directory, so it can be omitted when run from the repository root.

The consuming repository owns its project logs, `AGENTS.md`, `lbkit.yaml` and `lbkit-skills.yaml`. lbkit owns the shared implementation and instructions. Installed links:

```text
.agents/skills/lb-*  -> ../../.lbkit/skills/lb-*
.claude/skills/lb-*  -> ../../.lbkit/skills/lb-*
bin/lb               -> ../.lbkit/bin/lb
bin/lb-anywhere      -> ../.lbkit/bin/lb-anywhere
bin/lbkit            -> ../.lbkit/bin/lbkit
docs/<shared>.md     -> ../.lbkit/docs/installable/<shared>.md
```

The installer links only entry points. The CLI implementation (`src/logbook_cli/`) stays inside the `.lbkit` submodule — `bin/lb` resolves it through its own path.

### Run from anywhere

`bin/lb` runs from the repository root. To invoke `lb` from any subdirectory of any consuming repository, link the wrapper once:

```sh
ln -s /path/to/repo/bin/lb-anywhere ~/.local/bin/lb
```

The wrapper finds the nearest parent directory with `bin/lb`. It runs that command from the repository root. This selects the repository's pinned lbkit revision.

## Refresh contract links after upgrading

The shared source directory is now `docs/installable/`. Consumer entry points remain `docs/<name>.md`.

1. Inspect local changes before updating the pinned submodule revision.
2. Run the installer with `--dry-run`.
3. Review the proposed links.
4. Run the installer without `--dry-run`.

The installer replaces only recognized old contract links that target `.lbkit/docs/`. It refuses unrelated links or regular-file conflicts. Existing configuration remains unchanged.

## CLI dependencies

The CLI now uses Click. After upgrading the pinned submodule, rerun the installer to synchronize its environment. `bin/lb` use `.lbkit/.venv`; they never install dependencies implicitly. A missing environment produces an actionable error. The standalone installer itself needs only Python's standard library.

For local lbkit development, run `uv sync --locked` from the lbkit checkout. The consuming repository's Python environment is separate.
