# Status observation

Status reads records and runtime information. It never writes, syncs or runs GC; maintenance belongs to a separately authorized update. Live observation establishes no listeners, repairs no environments, runs no business commands, and controls no agents.

## recorded mode

Read the designated logbook, existing returns, and decisions; do not query live processes. State the source and its freshness; old records cannot prove "the current process is healthy". When live information is missing, report unknown — never escalate a record query into an environment investigation.

## live mode

When the user asks for live status, or an ordinary progress query involves an identifiable dispatched executor, read the adapter's read-only interface documentation and query status and recent activity with explicit identifiers. For a bound lbkit dispatch, use `bin/lb agent inspect LOG DISPATCH --thinking THINKING --live --json` first. It reports current identity and control readiness without sending. Missing or mismatched session identity means control is unavailable; do not substitute pane IDs or saved bindings. Use the environment-provided runtime skill only when a needed read is not covered by this adapter; never load or execute launch and recovery flows.

When query capability is missing or configuration is invalid, fall back to documented facts and state "live status unknown"; do not start substitute tools or change configuration. A missing session identifier does not prove no executor is running. Stagnation conclusions require activity timestamps and output evidence — never infer them from a single working snapshot.

Runtime status does not replace acceptance; old returns cannot override later logbook changes. Completion requires Captain checking and an authorized update. A standalone status request grants no execution authority; inside authorized lb-push, return to that caller so it can continue after answering. When live observation reads unsent text on an execution window's input line, distinguish client suggestions, verified human drafts and unknown input. None is proof of a completed action; unknown or suggested text grants no authorization and must not drive repeated checks or overwrite human drafts.
