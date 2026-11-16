# Document model and CLI layers

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
