# Configuration and Invocation Parameter Contract

lb-* skills use `lbkit-agents.yaml` at the consuming repository root (older versions live at `.agents/lb.yaml`; content unchanged — just move it to the root when upgrading), read and interpreted by the skills per this contract. Collaboration parameters such as host titles, Herdr, browser, and login hints live in the same file; see "Collaboration Parameters" below. This file does not declare any background program that auto-loads or executes configuration. Configuration selects implementations and fills in defaults; it grants no permissions. The authorization, isolation, focus, monitoring, and evidence boundaries in the consuming repository's `AGENTS.md` cannot be switched off through configuration.

## Defaults and Per-Run Parameters

Each call first pins down the target logbook and operation mode, then resolves the fields this run will use. Priority: explicit user specification this run → parameters explicitly recorded in the currently authorized work package → repository defaults. Launcher overrides may only pick declared candidates, never supply arbitrary commands. Only values matching the current authorization and the repository's hard constraints are valid; approval cannot be self-manufactured by writing override values into a work package.

There are no implicit extra project config files, environment-variable overrides, or "newest file wins". Natural-language parameters must also be made explicit within this run's context as same-named fields with sources, and choices affecting later handoffs are written into the existing work package or handoff record. Ordinary calls do not change repository default configuration; lb-status and read-only planning in particular must not write configuration back.

Mapping overrides field by field; lists are replaced wholesale. `runtime.launcher` is an atomic value — an override must supply both `command` and `args` together, and old launcher arguments are never spliced onto a new command. `runtime.launcher` and `launcher_alternatives` together form the selectable range; an explicitly chosen command + args must exactly match one of the options, and model and deployment metadata are read from that option, never improvised by the caller. Without an explicit choice, pick within the range per task needs and record the reason; prefer the default option when adaptability ties. No automatic failover.

All relative paths resolve against the managed repository root, not the skills directory or the current shell directory. Prefer the user-specified existing logbook, then the currently explicitly bound logbook; `project_root` only aids discovery — the root is not itself a project. When multiple projects cannot be uniquely determined, clarify instead of scanning the project repository. Without configuration, a uniquely identified existing plain Markdown file can still be processed; that never licenses guessing the runtime adapter or launch command.

## Fields

| Field | Type and meaning | Used by |
|---|---|---|
| version | Semantic version string; currently only 0.1.0 is supported. The legacy `schema: 1` is treated as 0.1.0, with a rewrite prompt on read | Entries that read the configuration |
| documents.adapter | mind-forge or markdown; selects how documents are maintained | Document reading and authorized writing by lb-* entries |
| documents.project_root | Non-empty path; `projects` in this repository, overridable to an approved directory | Entries that need project discovery |
| runtime.adapter | Non-empty adapter name; `herdr` ships with the kit today | push; status when requesting live state |
| runtime.launcher | Default launch option: `command` a non-empty string, `args` a string array, plus the model metadata below | push when creating or replacing a session |
| runtime.launcher_alternatives | Array of candidate options with the same structure; chosen per need, never auto-tried in sequence | push |
| limits.wait_seconds | Integer in 1–60; the wait cap for a single observation, default 30 seconds — not a project-task timeout or stagnation limit | push's waiting steps |
| limits.review_rounds | Positive integer or null; maximum rounds a candidate is submitted to independent inspection, including the first | plan's inspection design, push's review control, update's return judgment |

`review_rounds: null` means unconfigured — not an infinite loop, and not "no review needed". A current work package requiring independent inspection must have a finite round count before dispatch: it can be proposed explicitly per the task and confirmed along with the work package, or an existing explicit limit is carried over as-is. Tasks that need no review do not get checkers created just to fill this field. Round increases or resets never arise automatically from restarting sessions, switching skills, or changing candidates.

Launch commands and arguments are used as argv — never spliced as shell fragments, no eval, no command substitution, no inferring secrets from materials. The adapter tool's documentation is authoritative for actual invocation syntax. The default launcher's name proves nothing about its engine or permission mode.

## Collaboration Parameters

The following fields live in the same `lbkit-agents.yaml`; shared skills read them at the steps that need the values and never treat template values as facts. The installer copies the [template](../lbkit-agents.template.yaml) when the file does not exist and keeps any existing file.

| Field | When used |
|---|---|
| `roles.human_owner_label`, `roles.coordinator_label` | Display titles for the human owner and the coordinator; identity and authorization still follow the consuming repository's `AGENTS.md` |
| `runtime.herdr.workspace_id_env` | Environment variable name to read when Herdr is chosen and tabs must be created in the coordinator's workspace |
| `runtime.herdr.label_prefix` | Label prefix for new Herdr sessions, tabs, and panes; the template default is `^`, which the host may change to its own convention |
| `runtime.herdr.shell` | When the wrapped launcher is a shell function and must be verified inside an interactive shell |
| `runtime.herdr.permission_mode` | Tool mode used when the host has authorized auto-approval; this field never widens authorization |
| `browser.profile` | When authorized browser work genuinely needs an agent-specific profile |
| `auth.recurring_login_hint` | Login-cadence hint with a reliable existing basis; when empty, do not speculate about expiry frequency |
| `documents.mind_forge_guide` | Path to the host-provided mapping guide when the mind-forge document adapter is selected |

Paths are relative to the consuming repository root. Current values must not be inferred from `.lbkit/` templates, other repositories, command names, or past evals. When a value is missing, `null`, conflicts with host rules, or cannot be verified as genuine, first verify read-only within existing authorization; if the value is still needed to continue, tell the human the required field, its purpose, and candidate values, and wait for an answer. When an optional value is missing, skip preparations that depend on it instead of blocking unrelated work. When a consultation's outcome affects later work, the human or an agent authorized to maintain rules writes it back to the host file — never into the shared template.

## Model Selection and Data Boundaries

Every candidate option must also declare `model` (non-empty actual model identifier), `deployment` (internal / external / unknown), and `suitable_for` (non-empty array of task-fit notes). `suitable_for` is a selection hint, not a measured capability ranking; internal-deployment judgments require trusted configuration, platform documentation, or human confirmation — never inference from a command name, a model name, or an internal proxy address. Options with unverified provenance are marked unknown.

Before creating or reusing a session, determine data sensitivity from repository rules, user instructions, and actual inputs; filter candidates next; compare reasoning depth, context size, tool capability, latency, and cost last. Sensitive inputs go only to internal; when sensitivity is unknown, external and unknown are also off limits. Cross-repository tasks are chosen by the strictest input requirement. A local CLI or proxy never re-judges an external deployment as internal.

Choosing a suitable candidate within existing task authorization needs no per-instance model consultation; record the option, the reason, the data classification, and the deployment basis. If no suitable candidate exists, provenance is unclear, or launch is unavailable, report the exact gap — never fall back to directly launching codex/claude, switching proxies, or altering the candidate range. Changing the candidate range is a configuration change, not something derived from ordinary task authorization.

Model boundaries equally cover eval samples, subagents, retries, and recovery. Before reusing a session, verify the actual model and the applicability of its existing context before submitting material; repository content is never sent to a non-compliant model to satisfy a check. After launch and before dispatch, verify the actual model, deployment option, and permission parameters; stop dispatch on any mismatch.

### Wrapped Launchers

The consuming repository's `AGENTS.md` may whitelist launch commands. Passing a read-only configuration check proves nothing about service reachability, actual routing, or suitability for sensitive data.

Runtime parameters such as the task, output format, resume identifier, or disabled tools must not override the model, profile, provider, or proxy the wrapper binds; candidate and deployment limits must not be bypassed through command aliases, extra arguments, environment variables, or hidden subprocesses. The wrapper calling the engine internally does not authorize the coordinator to call the engine directly.

## Missing Values, Conflicts, and Validation

Validate structure, types, and values before using fields. When existing configuration fails to parse, the version is unsupported, a field spelling is unknown, or a value is out of range, report the configuration problem explicitly — never silently ignore it or quietly change defaults. When only the recorded logbook status is requested, an explicit downgrade to a read-only report of known documents is still allowed, but real-time verification must not be claimed.

Tasks that need no tooling do not require launcher, wait, or review parameters to be complete; existing session recovery does not force a new session. If a valid launcher is missing before creating or replacing an execution process, stop that step. Other runtime adapters are not implemented in the kit: they can be adopted only when the current environment provides explicit capability, parameter mapping, and authorization, and the consuming repository boundaries still apply. When the consuming repository explicitly requires Herdr-visible monitoring, never auto-degrade to polling or hidden subprocesses.

Do not turn authorization confirmation, evidence verification, worktree isolation, focus stealing, or monitoring start into boolean switches. Goals, repositories, checklist items, candidates, evidence, owners, and authorization bases are per-run work inputs, not hardcoded defaults.

## Per-Run Operation Modes

mode is a call input to the entry, not part of the global default configuration; it can be inferred from an explicit request, so users need not memorize parameter names.

| Entry | Modes | Key boundary |
|---|---|---|
| lb-plan | create / revise / review | review is read-only; taking over an existing plan is usually revise |
| lb-push | advance / resume / cleanup | cleanup handles only authorized resources; it does not dispatch project items |
| lb-update | format / evidence / close | New completion verdicts must go through evidence; format must not be used to bypass it |
| lb-status | recorded / live | Explicit recorded relies on records only; an ordinary progress query with a dispatched executor defaults to live, and missing capability is reported as explicitly unknown |
| lb-preflight | run | Read-only preflight with step-by-step feasibility analysis; blockers are written back as 🔮 after human confirmation; any unresolved 🔮 halts the whole logbook |

Status observation modes are separate from write permissions: recorded/live may both maintain emoji and a few fact snippets; when "read-only / no modifications" is explicitly requested, writing is forbidden. Stagnation is usually bounded by 10 consecutive minutes without effective progress, judged per the task's character; no fixed total task duration limit is added, and wait_seconds is not that limit.

For example, "plain Markdown, logbook at notes/demo.md, plan check only" maps to documents.adapter=markdown, an explicit logbook location, and lb-plan's review. No new YAML override file is needed, and repository defaults for the next call must not change because of it.
