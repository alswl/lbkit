---
name: lb-retro
version: 0.5.0-dev
description: "Consolidate cross-logbook lessons and skill adoption on the host main branch, using a fixed Git snapshot and a stable feedback ledger; does not dispatch project work, change goals, commit, push or publish."
---

Read the [document state and CLI failure recovery contract](../../docs/installable/document-state.md).
If lb is unavailable or crashes, notify the user and take over safe authorized work;
report pending writes and verification gaps instead of silently stopping or bypassing CAS.


# Cross-logbook retrospective

Use this entry when the human requests a cross-project retrospective, skill feedback consolidation or adoption review. Project close-out remains lb-update; routine execution remains lb-push. Read the host root AGENTS.md and the [operations contract](../../docs/installable/lifecycle-operations.md), [configuration](../../docs/installable/configuration.md) and [document adapters](../lb-update/references/document-adapters.md).

1. Determine the requested period, host main branch (master by default), permitted ledger(s) and approved project scope. Read a fixed main-branch revision with `lb feedback scan --since YYYY-MM-DD --ref master --ledger PATH --json`. A ledger must already exist; create one only under explicit host maintenance authorization. Do not switch branches, stash, pull or merge to prepare a retrospective. A non-main checkout may inspect the named ref; ledger writes require the main checkout. Uncommitted/unmerged records are outside snapshot coverage and must be disclosed.
2. Read each relevant original Thinking/feedback source. Separate a new incident from historical backfill; planned skill annotations from actual calls; existing rules not followed from a missing capability. Read attributed `lb skill usage LOG --thinking PATH` for identified tasks. Existing `lb skill extract` and authorized `lb skill history` are supporting observations, not proof of successful adoption. Never scan unapproved session stores or machines merely to complete a count.
3. Group semantic duplicates under stable finding IDs. Assign classification, responsible maintainer and source references. Keep disposition, implementation and adoption separate. An implementation reference does not verify behavior; an actual invocation does not prove effectiveness. Preserve previously closed/deferred findings and their source identity.
4. Present one concise numbered review of repeated issues, suggested improvements, adoption and evidence gaps. Significant direction, permission or capability problems discovered during execution must already have been raised by the project Captain; do not postpone them to retro. This entry does not create project todos, alter human gates or silently rewrite external skills.
5. For authorized ledger maintenance use `lb feedback show` to obtain its token, then `lb feedback record/update --input-file FILE --expect-version TOKEN --dry-run --json`, inspect, write and reread. Input JSON contains id, summary, classification, owner, source_ids, sources, disposition, implementation, adoption and verification. Identical record retries are safe; conflicting IDs require update. No source IDs are discarded on update. Keep explanatory prose readable next to structured records when authorized; never bury a required human decision in metadata.
6. Route accepted changes to lb-workflow, existing host policy maintenance or the shared skill/CLI maintainer under the actual authorization. This entry can apply authorized maintenance, but never commits/pushes/publishes or starts business execution. Record source IDs only after the finding is durably saved; incremental scan then suppresses those occurrences. Do not advance a time-only checkpoint over unsaved findings.

Report the inspected revision and period, recorded changes, remaining owners, local adoption, implementation and behavioral verification separately. A weekly invocation is optional; this skill installs no scheduler.
