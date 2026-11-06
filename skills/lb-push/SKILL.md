---
name: lb-push
version: 0.6.0-dev
description: "Advance or resume a confirmed Logbook through its authorized endpoint. Preserve explicit Captain takeover across subsequent tasks; otherwise dispatch Sailors or select automatic problem-specific takeover. Stop at human gates or concrete blockers. push means project advancement, not Git push; use lb-status for queries."
---

# Advance authorized work

## Purpose and inputs

Execute the saved route to its authorized endpoint, preserving human gates and
explicit steering. Push means advancing work, not Git push. Read host rules,
[configuration](../../docs/installable/configuration.md),
[coordination](../../docs/installable/coordination.md),
[document state](../../docs/installable/document-state.md), and the current
Logbook/context, relevant design, preparation and execution records.
Reuse applicable confirmation and authorization; do not ask again merely because
an executor returned or the user asked for status.

## Judge and execute

1. Reconcile current Task facts, dependencies, ownership and actual observations.
   Select the next authorized work. Unknown, paused and blocked tasks remain
   visible, with their actual exit conditions. A cancelled dependency is not done.
2. Compose lb-plan/lb-preflight when the next step lacks a saved route or relevant
   preparation. Inspect concrete changed prerequisites; avoid repeated unchanged
   plan/preflight cycles or unrelated environment sweeps. A real material choice,
   human gate or unavailable dependency is a specific stopping reason.
3. Execute within the established mode. Honor an explicit Captain takeover across
   its authorized scope and preserve pending handoff ownership. Ordinary delegation
   uses the current Herdr skill and [collaboration reference](references/herdr.md).
   Do not add an executor or independent reviewer merely to complete a small
   authorized task; required independent checks still remain independent.
4. Give Sailor a self-contained instruction: Task identity, work, inputs, constraints,
   desired outcome, verification and escalation conditions. Sailor does not read
   or write Logbook or call Task mutation commands. Captain alone records work,
   correlates replies and handles old instructions or in-flight replacements.
5. Require actual recipient acceptance/decline correlated to the sent instruction.
   Delivery, readiness, silence and idle do not establish acceptance. An accepted
   already-authorized instruction may execute immediately without another approval.
   A superseded reply cannot transfer responsibility for the replacement instruction.
6. While Sailors run, read Observation context and configure verified targets only
   when absent or changed. In Claude Code prefer native Monitor with managed wait
   --stream; foreground managed wait is the fallback. Reuse its listener across
   host yields. On notification read fresh context, then event defer/resolve or
   answer submit as applicable. Unknown/submitted delivery requires reconcile
   without resend. Separately authorized external UI handling uses prepare before
   the action and caller-evidence reconcile afterward. Follow the exact commands
   in [Herdr collaboration](references/herdr.md). Receipt, handling and business
   completion remain separate. For missing input, inspect authorized sources first,
   then ask the responsible person the smallest concrete missing decision.
7. Captain checks returned work against the actual contract and records canonical
   state through current-token CLI writes. Simple completion needs no mandatory
   Run, Result or invented start event. Record optional useful evidence; retain
   required candidate/independent-review checks. If a writer is unavailable, report
   the exact pending change honestly and continue independent authorized work.
   Close completed Task-specific takeover/handoff notes so they describe the
   finished responsibility. Preserve broader takeover scope and any real pending
   owner or in-flight work; a checked Task must not hide those obligations.
8. Continue with the next authorized action until the endpoint, explicit pause,
   real blocker or human gate. Answer an intervening status question read-only,
   then actually continue; a promise to continue is not the next action. A standalone
   status request authorizes no execution. Explicit stop/read-only steering wins.

## Runtime and lifecycle judgment

Separate Task pause from worker shutdown. Stop new dispatch when directed, inspect
in-flight work, and handle it through Herdr within actual scope. Do not close a
session solely because its Task paused. Keep uncertain delivery protected: inspect
before retry; a new operation ID does not make an unknown send safe to repeat.
Retain the in-flight binding and explicitly record that Captain owns its unresolved
handling and late replies, including in the pause status and handoff report.

Prefer foreground tool waiting and result handling within the current turn; this
requires no new-turn wake. Preflight records actual inner/outer yield limits and
model continuations over a long no-event window, plus working/tool-wait UI and
steer/queue behavior. No automated post-turn wake injection is provided. A detached
PID alone is insufficient; qualify that separate capability without rejecting a
working same-turn path or claiming unmeasured zero model polling.
Installation, skill discovery, runtime integration and session readiness are
separate observations. Missing/stale setup does not authorize personal hook updates.

Preserve host-configured runtime/model/permission restrictions and approved
workspace/cwd. Open/close only owned resources, without stealing focus. Do not
turn a terminal suggestion into human authorization or close unrelated resources.
Follow existing host delivery and cleanup rules; worktree deletion, commit, push,
merge and publication require their actual authorization.

## Output and exit

Report actual work and checks, remaining Tasks and precise blockers/gates with
current Logbook locators and usable delivery links. Attribute executor results;
keep business evidence in host-owned records. Do not claim whole-feature acceptance
from fixture tests or live compatibility from controlled observations.
