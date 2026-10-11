# 0.2 Feedback Changes and Acceptance

Date: 2026-10-11. Baseline: `a895349`; implementation is an uncommitted working-tree change. Input: the consumer's `docs/lbkit-feedback.md`, Issues 1–29, plus the owner's follow-up decisions: generalize delivery beyond software, require mind-forge, allow verbatim goal transcription, and keep source pointers rather than copied originals.

## Contract Decisions

- Create saves a draft before confirmation; a saved draft does not authorize execution. Explicit human goals may be transcribed verbatim with provenance in Thinking. Small work defaults to one Stage; confirmed workflow templates retain their structure.
- Skills appear only as names under their todos. Both bare names separated by `、` and legacy backtick lists remain extractable. Registry format stays 0.1.0; no new schema was necessary.
- Managed logbooks require mind-forge. The low-level standard-library CLI still reads Markdown for inspection, migration and tests; it does not prove managed-workflow readiness.
- Delivery, actual verification and required human decisions are separate facts. Criteria follow the result (research, writing, events, environment or software), not a mandatory software pipeline.
- A document may have one `sources/<doc-name>.md` containing authoritative pointers, identity, time and verification applicability. Originals remain at their source; Thinking preserves conclusions and decisions. Cleanup requires a viable retention/discard decision, not automatic archival into the coordinator's repository.
- Existing `[-]` items can be dispositioned with a sourced human decision. Closure with cancellation is distinguished from successful acceptance. Human work may move from not-started to in-progress; completion, cancellation and reversal remain protected.

## Migration Required

This is a breaking 0.2.0 release for shared contracts and `lbkit-agents.yaml`; all seven skills are 0.2.0. The optional skill registry remains 0.1.0.

1. Install a runnable `mf` before installing/upgrading lbkit; `mf version` and initialization failures now stop installation. Existing `minds.yaml` no longer bypasses the executable prerequisite. Installation preserves existing consumer config and instructions.
2. Migrate the consumer's agent configuration to `version: 0.2.0` and `documents.adapter: mind-forge`; provide its mapping guide and establish valid Prompt/Thinking bindings before managed logbook writes. Read-only diagnosis and explicit repository maintenance remain available. Do not silently overwrite old configuration.
3. Optional `limits.context_unknown_packages` defaults to 3. When context cannot be measured, rotate only at a safe completed-package boundary with handoff; credit/quota is not context usage. Existing measurable context policy remains >80%.
4. Replace generated SKILLS inventories with per-task names on future edits. Existing logs are not bulk-reformatted, and existing human wording is not silently rewritten.
5. Keep legacy preflight records and source locations as history; current preflight observations belong to bound Thinking, referencing a per-document source index where useful. Do not move/copy/delete raw materials merely to upgrade.
6. Review consumer-owned instructions for old blanket first-line/checkbox prohibitions or optional-mind-forge rules. This change does not overwrite them. The owner explicitly excluded AGENTS.md from this implementation.

New CLI commands: `task add --before-task`, `task rewrite`, and `task resolve`. Successful logbook writes return `version_token`; dry-run returns the unchanged current token. Existing flags remain available. Resolution metadata is an additive `处置：` JSON child bound to exact task text; stale or malformed records do not establish closure. CLI decision strings are records, not authentication of human intent.

## Feedback Coverage

| Issues | lbkit changes | Boundary |
|---|---|---|
| 1, 2, 8, 9, 16 | Draft-first planning, smallest useful Stage, template slots, per-task skills | Consumer workflow files are not edited by this change |
| 4, 5, 6, 7, 10 | Exact insertion anchors, returned token, explicit disposition, guarded rewrite, human progress | No force-close or human-completion bypass |
| 17, 18, 19, 20 | Registry/definition/environment distinctions, current decisions, refreshed route coverage, scoped blockers | No new provider-specific registry entries or consumer mutations |
| 13, 21, 22, 24, 25 | Current recipient entry, actual verification, per-result/per-destination applicability, identity before external writes | Fork branching, CI retry commands, build numbering and marketplace operations remain business-tool/workflow responsibilities |
| 23, 26, 28, 29 | Human-facing main log, reference indexes, original-location retention and cleanup responsibility | No default copying into sources and no automatic deletion |
| 3, 11, 12, 14, 15, 27 | Verified exit/keep boundaries, shell-history prerequisites, input provenance, pre-output redaction, review presentation, unknown-context fallback | No new Herdr API, no-history flag, context sensor or engine-side exit feature is claimed |

## Test-First Record

Before implementation, seven new CLI scenario tests failed (six failures and one missing-token error). Two installer expectations also failed: missing mf and failed mf initialization were previously accepted. Later, a new bare-skill-name extraction test failed before its parser fix. These were observable behavior failures, not source-wording checks.

Final deterministic acceptance:

- `python3 -m unittest discover tests`: **83 tests passed** (baseline 72).
- Focused feedback coverage: exact insertion and ambiguity; token chaining/dry-run/no-op/stale token; human progress without acceptance; protected rewrite and old-identity refusal; disposition invalidation/duplicates/fences/CRLF; all-cancelled closure; preflight refusal; bare skill extraction; required mf and failed initialization.
- Real installed `mf 0.4.2-dev+23b047c`: installation into an isolated initialized-submodule fixture passed, created the mind repository and exposed the source-index template. This did not create commits or contact a remote.
- CLI help/version passed (`0.2.0`); changed CLI modules and feedback test passed Ruff checks; `git diff --check` passed.
- Seven skill frontmatters parsed as YAML; 152 behavior scenario definitions have unique per-skill IDs and assertions/expectations; shared local file links outside examples resolve.
- The external skill-creator quick validator rejects the repository's pre-existing `version` frontmatter key. The repository-required version field was retained and actual YAML/name/version validation was performed separately; that validator rejection is not represented as a pass.

## Independent Behavioral Trials

Two fresh agents received only the revised skills, raw synthetic inputs and isolated writable mind-forge fixtures, with no expected answer or parent conversation. They used the installed mf and fixture lb commands. The coordinator inspected their resulting files rather than scoring their summaries alone.

| Trial | Observed result | Verdict |
|---|---|---|
| Research plan, half-day library interviews | Wrote `docs/interviews.md` immediately; one Stage; exact supplied goal; four unstarted tasks; unique Prompt/Thinking bindings; draft and missing execution inputs stated; no interview dispatch. `lb check`, article lint and project lint passed. | PASS |
| Research report evidence + human review started | Read R2 and I1–I3 originals; checked only the agent evidence item; human item became `[/]`, Stage remained 🚧. One `sources/interviews.md` referenced originals with identity/time/applicability; originals' hashes unchanged; registered with `--register-only --article ... --no-index`. No software gates. | PASS |

Trial source identities: report R2 sha256 `8544c5d10cd0936da45687e3b6447e03ef7dbe1af942f954e72dd9a425b48708`; original interviews sha256 `159e6da5b2d239aebd9b502f5e7bcd1fe7df644c7286a3a18b8a0d696dbe3ef6`. These are synthetic fixture records, not consumer evidence. Temporary trial artifacts are not a permanent audit store; only key findings and reproducible scenario definitions are retained here.

Behavioral grading requires the actual artifact or tool result for each assertion. Fabricated evidence, external actions outside the fixture, copied source originals, invented software gates, unauthorized dispatch, or human completion by the agent fail the core scenario. Verbal plans alone do not pass.

Twelve scenarios were added and conflicting legacy expectations were revised. **The 152 definitions are not 152 executed model tests.** Only the two independent workflows above were model-executed in this acceptance run; there was no old-skill model A/B comparison. Herdr dialogs/history/redaction/context telemetry, terminal rendering, remote execution, provider CI and fork/marketplace operations were not live-tested. Their updated contracts and unresolved upstream capability boundaries must not be reported as platform fixes.
