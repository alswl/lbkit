# Domain commands and lifecycle ownership

The CLI performs atomic operations. Skills decide whether an operation is authorized,
select its evidence, and sequence operations. A command never launches a skill, advances
the next task, or equates runtime success with acceptance.

| Object | Canonical commands | Lifecycle and authority |
| --- | --- | --- |
| Logbook | `log list/context/check/state/state-set/sync/create/report` | draft → ready → active; pause/resume, completion or termination are explicit decisions |
| Stage | `log state/sync` | derived from its checklist; no independent writable lifecycle |
| Task | `task identify/show/start/record-result/accept/cancel/reopen` | pending → active → submitted → accepted; cancellation and reopening retain identity |
| Dispatch | `dispatch create/list/show/set-status/attempt` | prepared → sent → acknowledged → returned → closed; cancellation requires no running attempt |
| Attempt | `dispatch attempt` | started → finished, failed or interrupted; a retry gets a new ID |
| Execution facts | `log execution context/record` | caller-attributed instructions/observations; derived delegation policy, not runtime orchestration |
| Agent | `agent bind/inspect/send/close` | saved binding is a claim; live state comes from the selected runtime |
| Workflow | `workflow list/show/check/create/update/set-status/diff` | draft → available → deprecated → retired; retired must reopen to draft |
| Skill | `skill list/show/check/usage/record-usage` | definition, readiness and usage are separate facts |
| Feedback | `feedback scan/show/record/update` | disposition, implementation, verification and adoption stay separate |
| Configuration | `config show/check/resolve/update`, `config agent ...`, `config recipe ...` | agents and recipes: draft → available → deprecated → retired; retired must reopen to draft |
| Toolkit | `lbkit doctor`, `lbkit adapter list/check herdr` | read-only diagnostics; `lbkit install` owns installation |

## Tokens and command boundaries

Use `--expect-version TOKEN` for the file being changed. Task mutations use the
Logbook token. Dispatch, agent binding and usage mutations use the explicitly resolved
`--thinking FILE` token. Preview with `--dry-run --json`, inspect the diff, then write.
CAS protects that one target file, not a multi-file transaction. Skills reconcile the
current logbook before acting on Thinking records.

The public root has exactly eight groups: log, task, dispatch, agent, workflow, skill,
feedback, config. Old command paths and option aliases are removed, not forwarded or hidden.
`config recipe` maintains work-type recipes in `lbkit-skills.yaml` through guarded atomic commands; `config agent`
defines launchable agents, while `agent` binds and controls live sessions. `skill extract` reads planned annotations,
and `skill history` reads authorized session records. These differ from `skill usage`,
which contains task-attributed outcomes. `log events record` records events; report
views live only under `log report`. Instance creation lives only under `log create`.

Task identities are registered explicitly; existing Markdown is never bulk-rewritten.
Once identified, use semantic task actions rather than checkbox/structural editing.
Historical completed items retain unknown evidence. Preserving human-owned document
bytes is independent of command compatibility.

## Task and dispatch example

```sh
lb task identify LOG --stage 'Stage 01 Build' --task 'Build @core' --task-id build --expect-version TOKEN
lb task start LOG build --basis 'Receipt observed' --expect-version TOKEN
lb task record-result LOG build --input-file result.json --basis 'Executor return' --expect-version TOKEN
lb task accept LOG build --candidate candidate-a --basis 'Applicable review passed' --expect-version TOKEN
```

`result.json` is `{"candidate":"candidate-a","evidence":["report reference"]}`.
The submission pins task text and acceptance/source/skill annotations. Changed criteria
invalidate it; acceptance requires the exact submitted candidate. Evidence references
are attributed input, not automatically verified reports. Human-owned tasks permit only
starting after actual human activity. Task IDs live in indented metadata below the item;
move that metadata with the item. Line numbers and wording are not identity.

A dispatch input JSON requires string fields `id`, `task_id`, `owner`, `scope`,
`exclusions`, `inputs`, `completion`, `escalation`. Create with
`lb dispatch create LOG --thinking THINKING --input-file FILE --expect-version TOKEN`.
Record each observed state using `set-status LOG ID --status STATUS --basis BASIS`,
and attempts using `attempt LOG ID ATTEMPT --status STATUS --basis BASIS`, with the same
Thinking/token options. Each command changes only Thinking. Returned/closed does not
accept the task. While paused, recording interruption and return remains possible;
starting or sending new work is refused. Cancellation records a decision; it does not
stop a process. Completion and session cleanup remain separate responsibilities.

## Runtime and skill inputs

`agent bind LOG ID` uses Thinking/token/input-file options. Its JSON requires
`machine`, `workspace_id`, `tab_id`, `pane_id`, `agent_id`, `session_id`, `observed_at`,
`basis`. Use full runtime handles. `agent inspect LOG ID --thinking THINKING --live`
reads the recipient and returns an observation token. Send/close additionally require
`--expected-session`, `--expected-observation` and Thinking token. Close also requires
`--basis`; send reads `--message-file FILE`, `--operation-id` and
`--expect-execution-version`, and journals its intent in the
[execution record](lb-cli.md#execution-state-in-project-json) before transport.
Preview does live reads but no control. A transport receipt is not an acknowledgement.
Reconcile unknown delivery before a new attempt; there is no automatic retry.
The runtime must expose a stable session identity: Herdr native `agent_session`
references need `kind: id`, a nonempty value and the matching agent kind. Conflicting
or path references refuse controls; pane identity cannot replace session identity.

lbkit owns adapter parsing, binding validation and guarded transport. It does not
install or repair runtime software, hooks, trust settings, launch configuration or
connectivity; a request to test or fix lbkit does not authorize that. Report an
unavailable external capability and continue independent authorized work.
Inspection and control are separate calls, not a transactional runtime compare-and-swap.

`skill check NAME --command EXECUTABLE` only checks executable discovery. It reports
authentication and full readiness as unknown. It never executes configured shell code.
Definitions come only from the selected repository. Usage JSON requires `id`, `task_id`,
`skill`, `state`, `outcome`, `basis`, `at` (ISO timestamp). States are declared, invoked,
observed; only observed permits effective/ineffective/failed, otherwise use unknown.
`skill record-usage LOG --thinking THINKING --input-file FILE --expect-version TOKEN`
pins the definition digest at the first record. Later definition edits do not rewrite
past adoption evidence. Captain aligns returned usage in lb-update; lb-retro consolidates
it on the host main branch without manufacturing project tasks.

## Workflow and delivery

New templates start in draft. After semantic review, explicitly set available using
`workflow set-status NAME --status available --basis BASIS --expect-version TOKEN`.
Only available and legacy unknown templates may instantiate. Retired templates may be
read and compared but cannot create runs. Existing runs pin their original digest.
`log create OUTPUT --from-workflow NAME --input-file FILE --expect-version TOKEN`
previews/creates one instance; document adapter bindings remain a separate skill step.
English template markers are `Run-instance template`, `Established rulings`, `Slot 1/2/3`,
`Title:` and `Working directories:`; legacy Chinese markers remain parser constants.

`log links record-check` stores an attributed observation; `log links audit` reconciles
required delivery entries. Neither performs remote authentication. `log report --view
closeout|metrics` composes recorded facts without accepting, cleaning up, or publishing.
Toolkit config checks cover YAML structure and core declarations, not full policy,
authentication, provenance or permission validation. No diagnostic performs repair.
