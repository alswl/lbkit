# Document state and CLI failure recovery

Logbook and Thinking Markdown are human entry points. Machine records live in
the project's `lb/` directory, a peer of `docs/` and `thinking/`. The project is
the nearest ancestor containing `mind.yaml`, otherwise `--root`. Each mind has one
state file named after its Markdown file: `docs/delivery.md` and
`thinking/delivery.md` share `lb/delivery.md.json`, beside the execution JSON
`lb/delivery.json`. Track Markdown and `lb/` state together in Git. These are
consumer-owned files; installation does not create or replace consumer records.
Legacy task Resolution/Resume annotations have a bounded compatibility reader and
explicit `task migrate`; other retired inline machine blocks remain unsupported.

A task may carry one indented `<!-- lb-task task-example -->` line. This is a
stable ID, never JSON. Keep goals, task wording, order, checkboxes, human gates,
criteria and useful evidence links readable. Do not add structured audit dumps
to the body. Unidentified tasks remain valid and need no state file.

The JSON envelope has `format: "lb-document-state"` and `documents`, a mapping
from project-relative Markdown path (for example `docs/delivery.md`) to that
document's section. A section maps record kind to ID to object; each document's
token and CAS cover only its own section. Kinds include document identity, task,
lifecycle, dispatch, agent, link-verification, workflow, workflow-status,
skill-usage, retro and run-event. Singleton records use `singleton`; run events
use the JSON-encoded pair `[run_id, event_id]`. Files use sorted keys and indented
JSON. Document UUIDs live under `documents.<path>.document.identity.uuid`. The
separate execution JSON retains its existing facts and send-recovery journal;
execution names cannot end in `.md`.

## Identity and consistency

- Rename a task without changing its ID. Task text, Source, Acceptance and Skills
  still bind evidence through a digest; editing them can invalidate the recorded
  candidate. Keep the previous submission and acceptance as history; do not
  manufacture a new pass. Reopening preserves historical snapshots.
- Move a task together with its short ID within the same document. Identity is
  independent of line number and order. Reassess the destination's human gates
  and stage-specific evidence. Never infer authorization from a move.
- Copying a task requires a fresh ID and fresh state. Duplicate IDs, missing
  records, orphan records and a record key that disagrees with its ID are errors.
- Deleting the task or its ID does not delete state or mean cancellation. Check
  reports the orphan and affected task operations refuse. Restore the binding;
  for an authorized cancellation retain the task and use the cancellation flow.
  Automatic garbage collection and cross-document task transfer are unsupported.
- A rename changes the state file and section key. Rename `lb/<name>.md.json` and
  its section path with the document, retaining its document UUID. Dispatch and
  agent records bind to the Logbook UUID; their saved paths are location hints.
  Host document bindings, execution paths and other links still need coordinated
  updates before affected operations resume. Copying an entire document with its
  UUID is not a new workflow instance; create a fresh instance instead.
- A manual checkbox edit does not silently change lifecycle or accept a result.
  `log check` reports disagreements and stale acceptance; task transitions refuse
  mismatched state. Human ownership and preflight protections continue to apply.
- Commit/review Markdown and `lb/` state together under host authorization. Different
  record IDs may merge independently. Conflicting changes to one ID, a deletion
  versus an update, different candidates, or incompatible acceptance decisions
  require explicit resolution. Never choose the latest timestamp as authority.
  JSON duplicate keys and conflict markers are invalid. Use `log check --all` to detect duplicate document UUIDs among discovered
  Logbooks. Run `log check` after
  merging even when Git reports a clean merge; inspect cross-document references
  and human decisions too. The CLI does not prove semantic merge correctness.

## Concurrent writes and interrupted transactions

Get `version_token` from `log context --json`. Document tokens hash length-framed
Markdown bytes plus its canonical state section (including absence); do not calculate a plain
Markdown hash. Successful writes return the resulting token, including no-ops.
Dry-run returns the original token and both diffs, and creates no files.
Execution/configuration JSON keeps its own existing token contract.

Cooperating readers and writers lock the approved root directory on macOS/Linux.
Writers reread Markdown, the document's section and declared dependencies before
replacing files, and keep other documents' sections. A record edit in the section
invalidates an old token; JSON whitespace does not. This is local coordination, not a
distributed Git lock; editors that bypass the protocol can still race with writes.

For a refused local record write, reread the named context and compare the current
records and criteria with the attempted change. If the cause was a malformed
input or copied token and the same change remains authorized and missing, correct
the invocation, extract the token programmatically, preview and finish the write.
A refusal alone is not a reason to stop after rereading. If criteria changed,
reassess the evidence first; do not merely refresh the token and replay acceptance.
Stop retries when the cause remains unresolved or another conflict occurs, and
report the remaining change. This procedure never retries an uncertain runtime send.

Two files cannot be atomically replaced together. The writer durably records
before/after images in `lb/<name>.md.transaction`, then publishes each file.
Readers of every document of that mind refuse unfinished transactions. Keep this
temporary journal and the execution `lb/.lock` local; add `lb/*.transaction` and
`lb/.lock` to the host's ignore rules. Inspect recovery before completing it:

```sh
lb log recover logbook.md --dry-run --json
lb log recover logbook.md --expect-version RECOVERY_TOKEN --json
```

Recovery rolls forward only if every affected file matches a recorded before or
after image. It refuses later edits and unsafe paths. The recovery token is for
that journal only; reread normal context after recovery. Never delete a journal
to conceal an interrupted write. Runtime sends retain their separate unknown
outcome protocol; document recovery must never resend a message.

## Skill fallback when lb fails

All lb-* skills follow this procedure when the CLI cannot start or crashes:

1. Tell the user promptly which command failed, its concrete error, and the
   affected operation. Distinguish a CLI outage from a normal validation/CAS
   refusal or a business failure. Do not silently claim the write succeeded.
2. Use a bounded invocation timeout and inspect the known local entry/environment once within authorized scope. Fix
   an invocation mistake when possible; do not loop, auto-install, upgrade,
   widen the root or launch another executor just to bypass failure. If only the
   launcher is broken, use the already-installed repository environment's
   `python -m logbook_cli` with the same approved root and current tokens, after
   verifying that it loads this pinned checkout. This is the same guarded writer.
3. Take over the useful work: read the exact Markdown, `lb/` state, host bindings and
   existing decisions directly; inspect actual executor returns and deliverables.
   Report current facts with explicit unknowns. Continue already-authorized work
   whose prerequisites remain verifiable; an outage alone is not a new human gate.
   Status-only requests still authorize no execution.
4. Preserve IDs, candidate/evidence bindings, human gates and authorization. For
   writes, use a functioning approved entry or a host writer that preserves the
   same paired-file lock, CAS, validation and recovery protocol. Direct editing is
   not an excuse to overwrite state or recreate long JSON comments. A CAS refusal,
   malformed state or unknown transport outcome is not permission to bypass it.
5. If no safe writer exists during an authorized update, finish the useful
   preparation and deliver a **pending change, not applied** in the reply or an
   already-authorized work record. Name the document and stable task/record ID,
   current state, proposed state or exact replacement text, candidate and evidence
   references, and the human gates that stay open. A summary of the evidence or
   “record this after recovery” alone is not a pending change. For identified
   tasks, specify the applicable semantic action (such as `complete` or `pause`)
   and basis. Use a `record-result` payload and candidate check only when the
   actual work contract calls for recorded candidate acceptance. Do not fabricate tokens, timestamps or a full
   replacement state file. A failed, stale or incomplete return must retain its gap;
   tool failure alone neither accepts nor rejects a candidate. State which facts
   are **not yet recorded**, what was inspected directly, and which checks could
   not run. Continue independent work; defer only dependent writes/dispatches.
   A read-only request still receives observations only, without an unsolicited
   update patch. No new archive is required.
6. When the CLI recovers, reread both files, reconcile human edits and actual
   completed operations, then apply only the still-missing authorized changes.
   Preview and read back; never replay an uncertain send or duplicate a return.

Before reporting source locations without CLI context, read numbered physical
lines, for example with `nl -ba LOG` or `rg -n` matching the exact task. Count
blank lines and hidden ID comments. Cite the observed task line; never infer it
from rendered Markdown or count an unnumbered excerpt mentally. If a location
cannot be verified, use the path and stable ID/task text and say the line is
unavailable. Proposed future positions are not current source locations.

This fallback preserves the host's explicit writer restrictions and existing
execution roles. It does not require fresh approval for already-authorized work.


## Canonical Task migration

New semantic Task writes derive current state from the Markdown marker and
Blocker annotations plus the validated task disposition in `lb/`. Migrated task records retain identity and
historical evidence, without a duplicate current `status`. `task-archive` stores
removed tasks separately from active anchor validation. Historical submissions
and acceptance remain readable. Legacy records are not silently converted by a
read: preview `task migrate` with the current context token before applying it.
Unresolved legacy conflicts refuse migration. Markdown and sidecar changes retain
the shared CAS/transaction-recovery boundary; state-only changes use atomic replace.


## Task data ownership and inline compatibility

| Content | Owner and meaning |
| --- | --- |
| Task text, checkbox, criteria, evidence links | Human-readable Markdown; criteria changes invalidate applicable evidence. |
| `Depends: ID, ID` | Human/machine shared route constraints in Markdown. IDs refer to task anchors; only done satisfies a dependency. |
| `Blocker: reason` | Human/machine shared obstacle in Markdown. Pause/resume preserves it until explicitly cleared. |
| Prior state used by resume | Task record `resume: pending/active` in this document's `lb/` section; no new `Resume:` annotation. Missing prior state requires `--to`; invalid/conflicting/stale state refuses. |
| `Resolution:` / `处置：` | Readable disposition, decision/source and reason in Markdown; the structured `resolution` object lives in the task record. The exact readable projection and task-text digest must agree. |
| `<!-- lb-task ID -->` | The minimal join between the human task and its record. It is not an audit log. Keep it with the task when moving it. |
| Digests, actor/source attribution, submission/acceptance, historical snapshots | Task record in the existing state section. No parallel file or inline JSON. |

Cancellation writes a readable disposition and its structured record together.
`task resolve` also registers a short ID for a previously unidentified skipped
item, including an explicitly dispositioned human item. It does not change the
checkbox or authenticate the caller's decision. Reopen moves current disposition
and prior evidence into history, retains a readable historical disposition in the
body, and clears current cancellation/submission/acceptance. Repeated cancellations
never erase earlier evidence. Both split forms archive complete original content
and identity in `task-archive`; replacements retain readable origin and decision
notes, while original text digests stay in the archive. Archived evidence is
historical, not active state.

Reads accept exactly one valid legacy JSON Resolution, bound to the exact task
text and skipped checkbox. Reads never migrate. Duplicate JSON keys, multiple
annotations, invalid shapes, stale digests or a mixture of inline and stored
records are errors, even if a caller believes one copy is newer. The same applies
to conflicting Resume sources. Ordinary semantic actions refuse inline machine
records with an instruction to migrate first.

Preview `task migrate LOG --expect-version TOKEN --dry-run --json` and inspect
both diffs. Apply using that same token. Migration replaces inline Resolution
with readable text, removes inline Resume, and saves the original annotation
bytes and structured evidence in task history. Unidentified legacy tasks receive
a short ID in the same transaction. Existing IDs and historical human attribution
are preserved. Unsupported or ambiguous legacy states still refuse the whole
migration; no writes occur on dry-run or validation failure. Interruption uses
`log recover`, not manual JSON repair or a second storage layout.

Consumers must upgrade the CLI with these contracts before making new writes.
Older CLI revisions cannot read the new prose Resolution or stored resume state.
Choose the pinned revision and migration timing explicitly; no version bump or
consumer conversion is automatic. Keep both files when reverting or reviewing;
do not revert only one half of a migrated task.
