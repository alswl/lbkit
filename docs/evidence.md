# Evidence Model

This defines the shared meaning of evidence across skills; verification order, failure handling, and write-back gates are governed by [lb-update](../skills/lb-update/SKILL.md). The coordinator verifies returned results, while original investigation and project testing remain the responsibility of the owning agent.

## Identity and Applicability

A piece of evidence links an acceptance gate, the candidate's immutable identity, the original record, the inspection verdict, and the applicable time and environment. Identity follows the deliverable: source commits, a pinned report version or content digest, build digests, environment change records, and observation timestamps. Not every project has Git commits, PRs, deployments, or performance benchmarks.

Performance comparisons must verify candidate, inputs, platform, timing boundaries, cache state, and process model; a cold first compile, a warm-cache CLI run, and a resident HTTP request cannot be compared directly. Small differences are not asserted as regressions without verification, nor written off as noise outright.

A moved branch, a verbal summary, task counts, the existence of test files, or an idle process are not sufficient to prove acceptance. Runtime state can change at any moment, and evidence of it only proves the state of a given environment at a given point in time; old observations must not be written as current facts.

Insufficient evidence is not the same as a failed result. Changes to the candidate, the acceptance criteria, or the environment may invalidate some older evidence; historical facts are retained, passing results from different versions are not stitched together, and unrelated evidence is not mechanically discarded.

## Inspection and Verdicts

The independent checker differs from the implementer: for the same pinned candidate, it verifies original records read-only and does not modify deliverables on the implementer's behalf. The inspection verdict is pass, fail, or an actionable gap, and is tied to an acceptance gate; verification along the actual usage path carries more weight than a read-only summary.

Contract or report files already cited as evidence in comments, reports, or historical records should be updated in place under their original filename. If renaming is truly necessary, keep a redirect under the old name or note the succession at the new location; do not trade a broken evidence chain for the tidiness of a rename.

Evidence form is part of the acceptance gate too: when E2E, real-environment operation, quality reports, or screenshots are explicitly required, code inspection, builds, or static analysis cannot substitute at a lower bar. UI E2E evidence should cover key operations and state transitions; the number of screenshots is determined by the reviewable key steps, and a single final-state screenshot must not stand in for the whole path. When multiple quality participants verify jointly, each participant's valid report must be visible and traceable to the applicable candidate, original record, and verdict. Frontend page deliverables must, by default, be seen running in a local dev environment by a human before the checkbox is closed; static descriptions and DOM assertions from an agent cannot substitute for this first-hand check.

Process evidence such as review records, quality reports, and screenshots lands in the coordination repository (sources, thinking, and artifact lines in the main logbook), not in the project repository's code PRs; a project PR keeps only implementation code, required tests, and explanatory docs.

The coordinator's acceptance verdict distinguishes passed, failed, insufficient evidence, and pending human decision. The limited number of review rounds is set by the current work package and the [configuration contract](configuration.md); switching skills does not reset the count.

## Merging and Final Decisions

When a project has PRs, current-state evidence distinguishes open, closed-unmerged, and merged. The first two do not satisfy the merge gate; the candidate and the post-squash/rebase commit may differ, so a reliable correspondence is required. Results without a PR are judged by their own acceptance gates; do not invent a merge gate.

A human accepting a deviation is a new basis for decision, not a pass under the original standard. Project completion, work-package acceptance, project cancellation, and process closure are distinct facts. Display conventions are in [Logbook Format](logbook-format.md); the actual close-out flow is in [Verification and Close-out](../skills/lb-update/references/verification.md).
