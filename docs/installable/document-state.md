# Markdown authority and explicit synchronization

Markdown is the SSOT for document content, Task identity, state, conditions,
dependencies and readable artifact references. Current Markdown wins; JSON never
writes document state back. The nearest ancestor with `mind.yaml` is the project,
otherwise `--root`. Consumers own these files and choose when to adopt the new
contract; installation does not initialize or rewrite their records.

## Initialize and synchronize

Create the authorized Markdown first. Initialize a new run explicitly:

```sh
lb log init-state docs/delivery.md --name delivery --json
lb task identify docs/delivery.md --stage 'Stage 01 Build' --task 'Build feature' --task-id task-build --json
lb log sync-state docs/delivery.md --json
```

Optional repeated `--document PATH` associates other existing project documents
at initialization. Paths stay fixed for this revision. A run has one Logbook.
Old layouts conflict and are refused; there is no conversion or migration.

The sole structured file is `lb/<name>.json`, format
`task-document-projection`. Its sections are:

- identity: run ID and explicit document paths.
- documents[path]: source digest, stages and Tasks keyed by short ID; rebuildable.
- execution: Task responsibility, immutable bindings, result sources, authorization
  facts and send operations; independent facts, never erased by sync.
- monitoring: targets, cursors, retired targets, events, answers and revision; null means
  unconfigured, configured empty targets is valid.

Track Markdown and independent run facts together under host Git authorization.
Sync replaces only the selected document projection. It never copies or clears
runtime facts. Do not edit JSON as a substitute for the supported CLI.

## Read and edit

Queries read current Markdown and expose missing/stale/synced. They never sync
implicitly. Document edits need no caller version token. They preserve normal
human confirmation, dependency, scope and input-path checks, and return
`document_saved` / `sync_required`. Explicitly run sync-state after an authorized
edit batch. The existing `log sync` edits stage markers and summaries; it is a
different action and still requires authority for that document maintenance.

A short indented `<!-- lb-task task-build -->` joins Tasks to independent facts.
Missing/duplicate/orphan IDs, invalid dependencies and ambiguous state refuse sync.
Move a Task with its ID; changed text is the same Task. Deleting/changing an ID
removes the active projection but preserves old runtime history. Never reuse an ID
for different work or infer historical identity from similar text. Split gives new
IDs and preserves the original in a readable fenced archive; it transfers no
execution permission. Readable Resume and Resolution annotations belong to Markdown.

Task runtime operations require current synchronized Markdown. Missing/stale
projections return sync_required. Existing receipt reconciliation and independent
monitoring continue even after document edits or Task deletion. A manual checkbox
is a document fact, not proof that an execution or human approval occurred.

## Results

Artifact links remain in Markdown. Use artifact → sync-state → result-source.
Source registration references an original same-Task binding or an explicitly
attributed subject and basis; started/finished records are unnecessary. Sources
are keyed by Task ID and exact ref. Changing ref A to B makes B's source unknown,
while A's historical source remains available. Same ref with conflicting provenance
is refused; use an explicit distinct versioned ref. Unknown versions stay unknown.
A link or source registration never completes or accepts a Task automatically.

## Failures and concurrency

Document save and sync are separate local operations. If document save succeeds
and sync fails, report the saved document and stale projection separately, fix the
specific problem and retry sync. Never roll back Markdown or repeat runtime send.
The source digest detects projection freshness; it is not a caller write token.
Short local locks serialize cooperating writers and atomic replacement prevents
partial files. Arbitrary editors do not join those locks: last Markdown save wins,
and the CLI cannot guarantee removal of every external-editor overwrite window.
No paired Markdown/JSON journal or global pending transaction is required.

Execution and monitoring writes retain their own context tokens and unknown-send
safety. A fresh token is not authorization to resend. Preserve unknown intent until
an actual receipt or explicit attributed observation reconciles it. Corrupt JSON
is refused, never replaced with empty execution or monitoring history.

For an unavailable CLI, continue useful authorized read-only work and report the
precise unapplied change: Task identity, current/proposed value and evidence.
Do not claim success or manufacture a token; source locators require actual numbered
reads. An outage grants no new permission or reason to repeat external effects.

Workflow instance creation publishes only Markdown and returns provenance for the
host document adapter to record. It never creates a document sidecar. Initialize
and synchronize the run explicitly after preparing its associated documents.

Consumer recovery uses current Markdown, CLI diagnostics and published contracts.
The presence of toolkit source in a submodule does not expand the host's source
access or development authorization. If those public surfaces are insufficient,
report the exact unfinished step and contract gap instead of inferring undocumented
state from the implementation.
