---
name: lb-cli
version: 0.6.0-dev
description: "Use the lb CLI to inspect or change logbooks, tasks, configuration and runtime bindings. Use for lb command selection, JSON inputs, version_token/CAS conflicts, human-confirmed task changes, Herdr resource creation or CLI failures. Collaboration planning and advancement remain with their owning lb skills."
---

# Use the lb CLI

## Discover the installed candidate

Resolve the consuming repository root and read its AGENTS.md. Use the repository's
actual CLI: `./.lbkit/bin/lb` in a consumer, `./bin/lb` in the source checkout, or
an explicitly verified installed `lb`. Preserve the caller cwd and pass `--root`
explicitly when the target is elsewhere. Do not install dependencies or change
providers just to run a read command. Report an unavailable CLI and continue useful
authorized read-only work; never replace guarded writes with raw state edits.

Read `--version`, `--help` and the selected command's `--help` from that same
candidate before assembling unfamiliar flags. Consult the [CLI contract](../../docs/installable/lb-cli.md)
and [domain commands](../../docs/installable/domain-commands.md) for schemas.
Do not use retired aliases or infer a command from an old session.

## Choose the object and operation

| Intent | Command family / source of truth |
| --- | --- |
| Read project tasks/state | `log context/check/state`, `task list/show`; context supplies document version_token |
| Change identified Task state | `task start/complete/pause/resume/block/unblock/cancel/reopen`; use its stable task ID |
| Change an unidentified checkbox | `task update --stage ... --task ... --status ...`; use exact current text |
| Change configuration | `config show/check/resolve/update`, `config agent/recipe ...`; read the configuration token |
| Inspect definitions and usage | `skill list/show/check/history`; availability is distinct from runtime readiness |
| Bind/send/observe a session | `agent bind/inspect/send`, `agent observation/event/answer/wait`; consult the operation-specific token/identity contract |
| Create Herdr resources | `herdr -- NATIVE_ARGV...`, `agent herdr open/close-session`; see below |

The CLI performs bounded operations; Skills own planning, delegation, interpretation
and acceptance. A status question remains read-only. Do not launch agents or write
progress simply because a next task is available. A transport receipt is not Sailor
acceptance or Task completion.

## Guard each write

1. Read fresh context for the exact target. Carry its version_token unchanged as
   `--expect-version TOKEN`; document, configuration, execution and Observation
   tokens are different authorities. Configuration uses `config show`, not log context.
2. Read exact inputs and the relevant contract; JSON files must resolve inside root.
   Use stable IDs for identified tasks. Never bypass identified lifecycle with update.
3. Use `--dry-run --json` when supported to inspect the candidate; preview grants
   no new authorization. A successful preview does not reserve a token.
4. Execute the authorized change with its applicable current token. Inspect output
   and resulting state; do not translate command success into business acceptance.
5. On CAS refusal reread and reassess the pending change. Never retry blindly or
   substitute a token from a different file. On uncertain runtime delivery inspect
   or reconcile the original operation; rereading a token does not authorize resend.

For human-owned task state changes, obtain explicit human confirmation first and
pass `--confirmed` on the task state command. Pending-to-active remains permitted
without it. For example, after the human confirms completion:

```sh
lb log context log.md --json
lb task complete log.md TASK_ID --basis 'Human confirmed completion' --expect-version TOKEN --confirmed --dry-run --json
```

Use the fresh token and the same authorized inputs to apply without dry-run.
`--confirmed` expresses the caller's already-received human confirmation; it cannot
manufacture consent, clear a preflight gate, bypass CAS/dependencies/state checks,
or authorize changes beyond the specific human instruction. Include the
confirmation basis in semantic commands. An unconfirmed human completion remains refused.

For separately approved human content, use `task note --confirmed` to add a
source/criterion or replace its exact same-kind annotation with `--replace-line`;
use `task artifact --confirmed` for the approved result. Use
`task rewrite --confirmed --decision SOURCE` for approved wording on an unfinished
human task. Rewrite preserves task ID, human ownership, repositories, checkbox,
position and children. Reopen a completed task through the authorized lifecycle
before changing its result criteria; confirmation does not waive this requirement.
Unconfirmed human details retain the additive Status exception only.

## Keep Herdr implementation boundaries

Sailor delegation selects a collaboration adapter; Herdr is its current concrete
implementation. Read the [Herdr guidance](../lb-push/references/herdr.md).
Use `lb --root ROOT herdr -- tab create ... --no-focus` or the corresponding pane
operation, with explicit host workspace/cwd/target and approved wrapper. The
prefix belongs to visible tab/pane names; never put it on the logical Agent ID.
`agent herdr open` is a native-runtime pane fallback, not a replacement for an
approved wrapper. Generic `agent open/close-session` no longer exist.

For recognized unsafe creation, B forwards original argv once and reports
configuration_not_applied; preserve native stdout/exit and append no rename/get.
Inspect the returned resource before relying on naming. Unknown commands pass
through. On partial naming failure retain known IDs; never blindly allocate again,
delete resources or rename an unrelated resource. The proxy does not replace guarded
business send. `config check` and `resolve` prove no runtime adoption.

## Report precisely

State the command/result and actual scope, with fresh file locators when useful.
Separate a proposed change, a preview, an applied write, runtime transport,
acceptance and publication. Name unsupported or NOT_RUN checks; keep human/Git and
consumer-upgrade permissions unchanged. See the [configuration contract](../../docs/installable/configuration.md)
and [document state contract](../../docs/installable/document-state.md) for details.
