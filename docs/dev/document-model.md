# Document model and CLI layers

## Model management principles

Use the Logbook as the single human-facing view of Tasks. Keep Task descriptions,
acceptance criteria, progress, and explanations readable in Markdown. The CLI
can consume Markdown where the document contract defines a stable, validated
format. Keep machine-only metadata out of Task text.

Extend the Task model with established concepts such as Assignee and Dependency.
Represent a dependency on work with a Task-to-Task relationship. Record the result
of an environment check as an Observation. Give a supporting record its own
identity only when the CLI needs to reference or manage it independently.

Store machine-managed records under `lb/`. Use the existing run file for data
that shares its lifecycle. A record type with a distinct write or validation
boundary can have its own run-scoped file. Task dependencies use
`lb/<name>.dependencies.json`. Reuse stable Task IDs across
files and let the CLI validate references.

Give each fact one authoritative source. The CLI rebuilds the Markdown
projection with `sync-state` and preserves independent runtime facts. When an
existing record type changes authority, define a compatibility rule and an
explicit cutover. Preserve route confirmation when a format change leaves the
reviewed content unchanged. Evaluate changes to dependency relationships as
route changes.

Before cutover, the Logbook still supplies the effective legacy dependencies.
Drain in-flight old CLI writers before installing this change. The first eligible
Run write publishes the typed dependency file and marks it authoritative. Read
and preview commands preserve the current source. A task replacement guards both
the Logbook and dependency file with a recoverable Run transaction. See the
[document-state contract](../installable/document-state.md#task-dependencies).

Managed self-check declarations are scoped to a confirmed Task and candidate.
The CLI validates the recorded authorization before saving a declaration in
the Run. The execution token covers the declaration. See the
[route readiness contract](../installable/lb-cli.md#route-confirmation-and-task-readiness).

## Authority and representation

Markdown is the editable source of truth for document and Task facts. Semantic
types describe Task state, Stage state, ownership, annotations and skill chains;
localized labels, checkbox characters and emoji belong to the format boundary.
Services compare semantic values instead of rendered glyphs. A settled Stage can
contain cancelled Tasks and does not necessarily represent successful delivery.

The parser retains source ranges, original Task text, labels and line endings.
Skill extraction consumes parsed Task annotations rather than rescanning Markdown
with a separate Task regex. A Task without an action prefix remains a Task even
when excluded from skill-registry candidates. Fences and comments follow the
shared parser's rules.

Skill chains preserve order, slash prefixes, bare or backticked names and trailing
explanations. Ambiguous values retain their source and produce diagnostics rather
than silently dropping names. Bilingual field mappings are explicit; adding a
label does not establish arbitrary-language support.

Short Task IDs join document facts to independent execution and result provenance.
Heuristic text matching, similar filenames and nearby links do not establish
identity or acceptance. The [document-state contract](../installable/document-state.md)
defines the authoritative storage and synchronization boundaries.

## Layers

| Layer | Responsibility |
| --- | --- |
| `commands/` | Click registration, arguments, options and error mapping |
| `services/` | Compose use cases and enforce operation boundaries |
| `models.py` | Semantic Task, Stage and ownership values |
| `document.py` | Parse Markdown and expose source annotations |
| `format.py` | Labels and marker mappings |
| `storage.py` | Path admission, locks and atomic writes |
| `render.py` | CLI output |

Commands adapt input; they do not duplicate domain rules. Presentation writes
results to stdout and errors to stderr. The [CLI contract](../installable/lb-cli.md)
owns public routes, JSON fields, previews, exit codes and context-token rules.
Preserve unrelated human text and UTF-8/LF/CRLF behavior during authorized edits.

## Verification boundaries

Unit tests exercise parsing, semantic reduction, representation and protected
writes in isolation. Cover mixed labels, skill-chain ambiguity, actionless Tasks,
comments/fences, human ownership and original-byte preservation. CLI, installation
and real-runtime workflows belong to the external verification repository.
Passing one layer does not establish compatibility or acceptance in another.
