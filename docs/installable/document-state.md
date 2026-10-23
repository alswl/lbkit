# Document state and CLI failure recovery

Logbook and Thinking Markdown are human entry points. Machine records live in
the project's `lb/` directory, a peer of `docs/` and `thinking/`. The project is
the nearest ancestor containing `mind.yaml`, otherwise `--root`. Each mind has one
state file named after its Markdown file: `docs/delivery.md` and
`thinking/delivery.md` share `lb/delivery.md.json`, beside the execution JSON
`lb/delivery.json`. Track Markdown and `lb/` state together in Git. These are
consumer-owned files; installation does not create or replace consumer records.
There is no old-format reader or migration command.

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
   tasks, a concrete `record-result` input payload plus the applicable guarded
   transitions (including the acceptance candidate and basis, when justified)
   is a reviewable semantic patch. Do not fabricate tokens, timestamps or a full
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
