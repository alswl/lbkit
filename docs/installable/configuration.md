# Configuration contract

The consuming repository owns two configuration files: `lbkit.yaml` (lbkit settings
and launchable agents) and `lbkit-skills.yaml` (work-type skill recipes). Recipes
describe the repository's own skill set, which may include skills from any source;
lbkit reads them but does not own that choice. A missing `lbkit-skills.yaml` reads as
no recipes. Configuration
never grants execution, repository access or publication permission.

## Model

| File | Domain | Contents |
| --- | --- | --- |
| `lbkit.yaml` | `settings` | Document backend, runtime adapter, collaboration parameters, `default_agent` |
| `lbkit.yaml` | `agents` | Launchable agents keyed by stable kebab-case ID |
| `lbkit-skills.yaml` | `recipes` | Work-type skill combinations keyed by stable kebab-case ID |

An agent has `status`, optional `name` and `description`, `launcher` (a `command`
and `args` array), `model`, `deployment` (`internal`, `external`, `unknown`), and
`suitable_for` (text array). Launcher arguments are data, never shell-executed by
configuration commands. All launch choices use this single registry. An agent here
is a definition; `lb agent` binds and controls live sessions.

A recipe has `status`, optional `name` and `description`, `applies_to`, `excludes`,
`steps` (ordered skill names), and `companions` (objects with `skill` and `when`).
A recipe does not name an agent: which agent runs the work is decided per dispatch
from data sensitivity and fit. Applicability and exclusions are separate text arrays; the CLI does not interpret natural-language
prefixes. Skill names reference independently installed definitions, not other
recipes; availability/readiness is checked with `lb skill show/check` at use time.

An optional agent `provider` selects its provider quota hints in `settings.runtime.quota`.
IDs remain stable when descriptions change. Unknown fields are preserved, not
interpreted or silently removed. Do not store credentials, session handles, run
history or adoption results here. `lb agent` owns session bindings; Thinking owns
usage evidence. `config agent show` and `config recipe show` return an `object_digest` for
pinning the exact configuration used in execution evidence. Skill usage pins the
actual definition digest independently; recording a recipe is not proof of use.

## Collaboration parameters

`settings.documents` contains `adapter`, `project_root` and `mind_forge_guide`.
The current managed-document adapter is `mind-forge`; the host guide supplies
actual object mapping. Missing required values are resolved from authorized
read-only evidence or a human answer, never invented.

`settings.runtime` contains `adapter`, optional provider `quota` declarations and
`herdr` parameters (`workspace_id_env`, `label_prefix`, `shell`,
`permission_mode`). It contains no launcher or launcher alternatives.
`settings.roles`, `browser`, `auth`, and `limits` retain host collaboration
parameters; auth contains guidance only, never secrets. Limits include
`wait_seconds`, `review_rounds` and `context_unknown_packages`. Limits and quota
hints do not authorize new work, approvals or data access. Configuration paths
are relative to the host root. Missing optional values do not block unrelated
work; missing values required for the next operation must be verified or supplied
by the human. Do not infer them from templates or another repository.

Operation modes are per-call inputs, never global defaults. A read-only request
never initializes or migrates files. Do not turn authorization, evidence checks,
isolation, focus or visible monitoring obligations into configuration switches.

`settings.default_agent` is null or an available agent ID.

## Model Selection and Data Boundaries

Every agent declares `model` (non-empty actual model identifier), `deployment` (internal / external / unknown), and `suitable_for` (non-empty array of task-fit notes); `provider` is optional and names the `settings.runtime.quota` entry that applies to the option. `suitable_for` is a selection hint, not a measured capability ranking; internal-deployment judgments require trusted configuration, platform documentation, or human confirmation — never inference from a command name, a model name, or an internal proxy address. Options with unverified provenance are marked unknown.

Before creating or reusing a session, determine data sensitivity from repository rules, user instructions, and actual inputs; filter candidates next; compare reasoning depth, context size, tool capability, latency, and cost last. Sensitive inputs go only to internal; when sensitivity is unknown, external and unknown are also off limits. Cross-repository tasks are chosen by the strictest input requirement. A local CLI or proxy never re-judges an external deployment as internal.

Choosing a suitable candidate within existing task authorization needs no per-instance model consultation; record the option, the reason, the data classification, and the deployment basis. If no suitable candidate exists, provenance is unclear, or launch is unavailable, report the exact gap — never fall back to directly launching codex/claude, switching proxies, or altering the approved agent registry. Changing the approved agent registry is a configuration change, not something derived from ordinary task authorization.

Model boundaries equally cover eval samples, subagents, retries, and recovery. Before reusing a session, verify the actual model and the applicability of its existing context before submitting material; repository content is never sent to a non-compliant model to satisfy a check. After launch and before dispatch, verify the actual model, deployment option, and permission parameters; stop dispatch on any mismatch.

### Quota Watermarks

Before dispatching or reusing an executor, read the current usage of each configured provider from what the provider actually shows (status-line 5-hour / 7-day usage, `weekly N% left`, and the like). Above `prefer_other_above`, new dispatches go to another eligible provider with headroom; running packages are not interrupted. Above `pause_above`, pause that provider's executors: no new dispatch or reuse, idle sessions exit after saving the handoff and the resume command, until the human lifts the pause or resets the quota. Unreadable usage is reported as unknown and never guessed; a status line without a quota warning counts as headroom. The coordinator's own provider is not paused but should avoid large reads and writes. Record any switch or pause and its reason in the handoff. Quota is a selection constraint after data-boundary filtering, never a reason to widen the approved agent registry.

### Wrapped Launchers

The consuming repository's `AGENTS.md` may whitelist launch commands. Passing a read-only configuration check proves nothing about service reachability, actual routing, or suitability for sensitive data.

Runtime parameters such as the task, output format, resume identifier, or disabled tools must not override the model, agent, provider, or proxy the wrapper binds; candidate and deployment limits must not be bypassed through command aliases, extra arguments, environment variables, or hidden subprocesses. The wrapper calling the engine internally does not authorize the coordinator to call the engine directly.

## Lifecycle

Create always starts at `draft`. Legal transitions are:

- `draft → available` or `draft → retired`.
- `available → deprecated`.
- `deprecated → available` or `deprecated → retired`.
- `retired → draft` (review again before making it available).

Only retired objects can be removed. The `default_agent` cannot be deprecated,
retired or removed; change the default explicitly first. The CLI never cascades.
Available means approved for selection, not installed, authenticated or running.
Skills select only available entries and verify actual capabilities separately.

## Commands and guarded writes

```text
lb config show|check|resolve|update
lb config agent list|show|create|update|set-status|remove
lb config recipe list|show|create|update|set-status|remove
```

Each leaf supports `--root DIR` and JSON output. Reads return the `version_token` of
the file holding the object (`config show` and `config check` cover both files); `show`
also returns the object digest. Recipe writes require an existing `lbkit-skills.yaml`;
copy `.lbkit/lbkit-skills.template.yaml` when the installer did not create it. Existing-file mutations
require `--expect-version TOKEN` for that file. Create/update/set-status read one YAML or JSON
mapping with `--input-file FILE`; `set-status` accepts only `status`. Update is a
recursive field patch: omitted and unknown fields survive. Lists are replaced as
units. Use null to clear an optional reference. Status is changed only through
set-status. Commands modify one agent or recipe, validate all references before
publication, support `--dry-run`, and return a diff. CLI writers are serialized
and reject stale tokens. External editors do not participate in the CLI lock;
byte checks detect edits observed before atomic replacement.

`config resolve [--agent ID] [--input-file overrides.yaml]` returns settings,
field sources and the selected agent/digest. Overrides contain only `settings`;
the explicit agent option wins over overrides, which win over stored settings.
Resolution neither writes configuration nor starts agents or skills. Skills own
selection, authorization, orchestration, and evidence judgment.

## Older files

The CLI reads only the current format and ships no migration commands. If a host
still has `lbkit-agents.yaml` or `lbkit-skills.json`, the agent maintaining its
configuration rewrites them into `lbkit.yaml` and `lbkit-skills.yaml`: settings and
launchers become `settings` and `agents`, skill entries become `recipes` with explicit
`applies_to`/`excludes`. New objects start as draft. Show the diff for human
confirmation, run `lb config check`, and delete the old files only when the human
agrees. The installer only creates missing files from their templates.
