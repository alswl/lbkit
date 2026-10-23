---
name: lb-workflow
version: 0.5.0-dev
description: "Create or refine reusable run-instance workflow templates and validate them through the lb workflow CLI; preserve human goals and gates, record provenance, and never dispatch execution or rewrite existing instances."
---

Read the [document state and CLI failure recovery contract](../../docs/installable/document-state.md).
If lb is unavailable or crashes, notify the user and take over safe authorized work;
report pending writes and verification gaps instead of silently stopping or bypassing CAS.


# Maintain workflow templates

Use this skill to create/refine templates, not to dispatch work or rewrite instances. Read the host AGENTS.md, [planning](../lb-plan/references/planning.md), [format](../../docs/installable/logbook-format.md) and [atomic operations](../../docs/installable/lifecycle-operations.md#workflow-cli). Read [document adapters](../lb-update/references/document-adapters.md) when maintaining companion records. Host-owned workflow documents are ordinary Markdown, not mind-forge projects or index entries.

1. Run `lb workflow list --json` and `lb workflow show NAME --json`. NAME is the directory name, not a path. Inspect available source instances and their Thinking; ask for a source only when needed. Without a confirmed goal, retain a human placeholder. Explain applicability and exclusions.
2. Review retain/parameterize/optional/remove choices against human-confirmed goals, tasks and gates. Existing maintenance authorization covers its stated scope; new semantic changes need a decision. Preserve irreversible operations as explicit human gates, not optional substeps. Use one Stage unless distinct acceptance or ownership requires more. Keep runtime facts in instances/Thinking, not templates.
3. Prepare one candidate for `workflows/NAME/docs/NAME.md`. Preserve stable constraints in `prompts/NAME.md` and source decisions in `thinking/NAME.md`; use lowercase hyphenated names. The template needs `## Run-instance template` before `## Established rulings`, three slots (date, machine-grouped directories, rulings), an explicit `Title:` and filename, fenced YAML front matter (`workflow`, `prev-run`) and fenced Markdown instance body. Preserve overview goal/non-goals, Stage titles, ordered tasks and manual gates; do not add independent Stage goals or a skills inventory. Put skill names on task annotations. Use a standalone `<WORKDIRS>` or contiguous directory list; keep ruling prose outside it. Make environment differences placeholders or optional substeps, not new tasks.
4. For a new template, prepare its approved docs directory and preview `lb workflow create NAME --content-file FILE --dry-run --json`. For an existing one, preview `lb workflow update NAME --content-file FILE --expect-version TOKEN --dry-run --json`, using show's token. Inspect the protected diff, then apply without `--dry-run` and reread. Each command writes one file; separately maintain authorized companions and report any partial state. Run `lb workflow check NAME --json`: it checks structural markers, not semantics or successful use. Fix unsupported layouts through authorized template maintenance, never by scaffold improvisation.
5. New templates start in draft. After authorized semantic review, use `workflow set-status --status available` with the current token and decision basis; deprecated/retired templates cannot create new runs. See the [domain contract](../../docs/installable/domain-commands.md). Record the source decision briefly in workflow Thinking. Keep contract validation separate from actual instance evidence. Do not propagate edits into existing runs; discuss any effect on an in-flight run separately. `lb workflow diff LOG` reports drift from the pinned content digest; no version bump is automatic. Hand instance creation to lb-scaffold and cross-logbook learning to lb-retro.

Common lifecycle, event recording and delivery-link checks belong to skills/CLI, not boilerplate tasks in every template. Preserve explicitly required domain cleanup and handoffs; do not impose new hidden gates on old tasks. Installer conflicts preserve host copies; migration requires explicit maintenance authorization.
