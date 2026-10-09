# Status observation

This reference only defines reading records and runtime information; permitted local document maintenance is governed by the skill's main workflow and the logbook format. Live observation establishes no listeners, repairs no environments, runs no business commands, and controls no agents.

## recorded mode

Read the designated logbook, existing returns, and decisions; do not query live processes. State the source and its freshness; old records cannot prove "the current process is healthy". When live information is missing, report unknown — never escalate a record query into an environment investigation.

## live mode

When the user asks for live status, or an ordinary progress query involves an identifiable dispatched executor, read the adapter's read-only interface documentation and query status and recent activity with explicit identifiers. For Herdr, use the environment-provided tool skill; never load or execute launch and recovery flows.

When query capability is missing or configuration is invalid, fall back to documented facts and state "live status unknown"; do not start substitute tools or change configuration. A missing session identifier does not prove no executor is running. Stagnation conclusions require activity timestamps and output evidence — never infer them from a single working snapshot.

Runtime status does not replace acceptance; old returns cannot override later logbook changes. New completion conclusions go to lb-update for verification, and resuming execution goes to lb-push — a status request grants neither. When live observation reads unsent text on an execution window's input line, handle it as an intent signal per the root rules.
