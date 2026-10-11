# Evidence and Source References

Evidence supports an agreed result, whether a study, article, event, operational change, or software deliverable. [lb-update](../../skills/lb-update/SKILL.md) verifies returns; [coordination](coordination.md) defines responsibility and authorization. Do not manufacture development, publication, or human-review gates for unrelated work.

## Identity and Applicability

For each acceptance criterion, identify the result, original observation, applicable environment or audience, time, and verdict. Use the identity appropriate to the work: a document revision, dataset snapshot, event/date, environment change record, or content digest. A summary, planned check, process exit, or result from another subject is not proof that this result passed.

Separate preparation, delivery, actual verification, availability to the intended recipient, and any required human decision. Check only the dimensions required by the agreed goal. Record verification as passed, failed, not run, cancelled, not applicable, or unknown according to the actual record; an aggregate success label cannot turn an unexecuted required check into a pass. For example, a rehearsal at another venue cannot validate this venue, and a different build event cannot validate this candidate's required check.

Changed goals, result identity, inputs, environment, or criteria invalidate affected conclusions, not all history. Reuse evidence only with an explicit, verifiable applicability argument; preserve the original observation's identity and date. Identical content may share content-based evidence, but that alone does not prove a new environment or recipient was verified. Runtime observations prove a condition at the observed time, not permanent correctness.

## Verification and Decisions

Use the required form of evidence: direct observation, interviews, independent review, measurements, real-environment operation, or other agreed methods. Do not substitute an easier check. When independent review is required, the checker differs from the producer, inspects the same fixed result, and returns original-record references and a verdict without editing the deliverable. Review rounds remain bounded by the work package.

The coordinator distinguishes passed, failed, insufficient evidence, and pending human decision. Human acceptance of a deviation is a new decision basis, not proof that the original criterion passed. Record an applicable explicit decision directly; do not ask for it again. Completion, cancellation, acceptance, and process closure remain distinct.

When external delivery is required, verify the real current destination and status. Provide the recipient's actual entry point; do not substitute an intermediate report, a historical delivery, or a guessed URL. Object identifiers plus a verified lookup location are acceptable when the platform provides no stable web URL. Domain-specific release, review, or installation mechanics belong to the relevant business skill, not this contract.

Verify repository delivery against the current candidate only: a CI, build-artifact or install success from another event is not a repository delivery, and a historical or older-candidate PR cannot impersonate the current entry; when no PR exists for the current candidate, record the candidate identity and the absence truthfully rather than substituting another event as a stand-in.

Different categories of delivered objects — source baseline (Git tag/branch), build artifacts, platform releases, marketplace listings — are distinct identities; completing one does not substitute for the others, and re-verifying an unrelated category still requires its own evidence for the current candidate.

## Storage and Presentation

mind-forge is required for managed logbooks. The main document shows overall progress, conclusions, necessary limitations, and current human delivery or action entry points. Thinking holds key decisions, result identities, applicability judgments, and recovery information. Process reports and work packages are not automatically main-logbook artifacts.

A document `docs/<doc-name>.md` may have one corresponding `sources/<doc-name>.md` reference index. For directory-shaped articles, use the canonical article slug from mind-forge. Register and bind the index using the installed mf-cli interface and the host mapping; preserve an existing mapping rather than creating duplicate indexes. Use the [source index template](../../skills/lb-plan/assets/source-index.md) when an index is needed.

The index contains pointers, not copied originals: exact authoritative locations or object IDs, immutable identity/revision (sha256 for downloadable artifacts when available), observation time, relevant criterion, and verification outcome or availability limitation. Raw recordings, reports, binaries, scripts, and execution records remain where they were produced or in their authoritative platform. Do not download an entire object merely to archive it again when a verified reference suffices. An index is neither a second checklist nor proof that its targets have been verified.

Before accepting a return, the coordinator verifies the original evidence and ensures necessary references and conclusions are recoverable. Before authorized cleanup, the coordinator checks that references do not point exclusively into the resources being removed. Resolve temporary references to durable originals, or apply the user's explicit retention/discard decision and record the resulting verification limits in Thinking. Missing evidence needed for acceptance remains a gap; a desire to clean up does not waive it. Do not automatically copy evidence into sources or delete originals. Offline archival is an explicit exception, with a reason and authorized location.

Maintain referenced indexes in place. If a document is renamed, update its source mapping and incoming references through mind-forge; do not erase historical observations or leave cleanup-dependent links in the main logbook.
