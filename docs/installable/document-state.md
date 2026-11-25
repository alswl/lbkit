# Markdown authority and explicit synchronization

Markdown is the SSOT for document content, Task identity, state, conditions and
readable artifact references. The Run's dependency file owns Task relationships
after cutover. The nearest ancestor with `mind.yaml` is the project,
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
at initialization. Those paths are fixed at initialization. A run has one Logbook.
Initialization refuses legacy execution records bound to the Logbook regardless
of the requested filename. A legacy sidecar section for any selected document
or a pending transaction for its sidecar also refuses initialization. When
documents share a filename, their sidecar sections are identified by project
relative path. For example, `lb/work.md.json` may retain only an archive section
while another `work.md` is initialized and synchronized. A section for a selected
document still conflicts in a valid sidecar renamed to a file such as
`lb/retained.json`. When `lb/observations/` exists, each
entry must use the UUID of a different document. The UUID needs one claim
across recognizable sidecars, including renamed copies. The sole claim must
come from the owner's project-relative section in its corresponding sidecar,
such as `lb/<document>.md.json` or `lb/<document>.markdown.json`.
This covers UUID-named JSON, listener locks and action locks. Initialization
leaves those files and sidecars byte for byte as found. Unknown or ambiguous
owners and unsafe paths refuse initialization. The path-keyed layout under
`lb/observations/<root-relative-document-path>.json` and its corresponding locks
still refuse initialization, including when the document has no sidecar. Use
[explicit legacy migration](lb-cli.md#legacy-run-migration) for eligible old runs.

For an existing run, context and synchronization still check for sidecar
sections and unfinished transactions across all bound documents. A migrated run
can retain the original sources verified against its published migration manifest.
Missing or invalid UUIDs in unrelated sections do not block those operations.

The authoritative structured file is `lb/<name>.json`, format
`task-document-projection`. Its sections are:

- identity: run ID and explicit document paths.
- documents[path]: source digest, stages and Tasks keyed by short ID; rebuildable.
- execution: Task responsibility, immutable bindings, result sources, authorization
  facts and send operations; independent facts, never erased by sync.
- monitoring: targets, cursors, retired targets, events, answers and revision; null means
  unconfigured, configured empty targets is valid.

A migrated run retains a private backup and keeps the verified legacy files in
place for rollback. They serve as historical evidence during unified authority.
Use the migration commands for authority changes.

Track Markdown and independent run facts together under host Git authorization.
Sync rebuilds the selected document's Markdown projection and preserves any
existing `documents[path].legacy_metadata` in place, including historical Task
dispositions, archives and link observations. A migrated run's top-level
`legacy_history` stays in place with its migration checksum. Other documents,
identity, execution and monitoring remain unchanged. Use the supported CLI for
state changes.

## Task dependencies

`lb/<name>.dependencies.json` stores the Run ID and an ordered set of Task
relationships. The main Run's `dependency_source` marks the authoritative file.
The first eligible Run write publishes the dependency file and then the marker
under the Run lock. This migration preserves the Markdown bytes and the effective
graph used for route confirmation. Queries and previews continue to read the
legacy annotations until the marker is published. New dependency edits use
`lb task depends` with the current `log route` reference. The CLI rejects missing
or invalid authoritative files, unknown Task IDs, duplicate edges and cycles.

Before deploying this change, drain already-started old CLI writers across the
project's `lb/` directory. Older CLI versions reject the new marker and can refuse
other Runs in the same directory. Keep the matching CLI, skills and contracts in
use across the project after cutover.

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
When a Task replacement changes both Markdown and the dependency graph, the Run
uses a recoverable transaction. An interrupted transaction blocks Run operations
until `lb log recover LOG --dry-run --json` has supplied a token and
`lb log recover LOG --expect-version TOKEN --json` has completed the changes.
Recovery preserves later edits by refusing unexpected file contents. Ordinary
Markdown edits and projection sync remain separate operations.

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
