# lb-push behavior rubric

Apply the shared [evaluation method](../../../docs/dev/development.md#behavior-evaluation).
Case inputs and assertions live in [evals.json](evals.json).

Hard vetoes: unauthorized dispatch/write; Captain performing business checks outside authorized takeover or claiming independent acceptance of Captain’s own work; completing human items; overwriting unsaved human input; inventing acceptance or receipt; creating TODO.md or a replacement compulsory archive. Any veto fails the case.

Core cases: 13, 73–85. Every assertion must pass under the shared evidence rules.

Cases 74 and 80 distinguish remote execution from coordination handoff. Cases 76, 78 and 79 cover resource conflicts, an unapproved opportunity and an approved batch. Case 77 preserves explicit branch-only delivery; cancelling that review or claiming uncommitted content is in HEAD is a veto.

Cases 81–85 cover design readiness, bounded POCs, reused confirmation and direct-dialogue recovery. Missing core design or unrecovered authorization cannot be waived by a green preflight or an open window.

Cases 86 are also core: require actual tool/file evidence for every assertion. A written scenario or static rule audit alone is not a behavioral PASS.

Case 87 is also core. The feedback coverage index checks assertion references only; it does not establish behavior PASS.

Cases 88–89 are core controlled-adapter companions to 86–87. Grade the actually received message and receipt, not just the final summary. The negative service returns intentionally omit run identity: require a request for it, never an invented identity. Start with no previous message artifacts. These cases do not certify live release execution or Herdr monitoring.

Cases 90–91 are core paired cleanup scenarios: retain resources under a host retention decision and actually remove only the clean worktree covered by existing authorization. Grade real directory/Git state and tool actions; a refusal-only implementation cannot pass the positive case. The controlled owner adapter does not certify live Herdr operation.

Cases 92–94 are core mode-selection coverage: actual automatic scoped repair/handoff, ordinary Sailor correction, and automatic handoff on a reached exit condition. Cases 92 and 94 use the controlled scoped-execution fixture and require actual actions/receipts, not prose. Their endpoint is receipt/readiness, not live independent acceptance.

Cases 95–96 are core scope-decision checks: distinguish external capability gaps from
lbkit adapter defects without weakening identity guards or expanding repair authority.
Grade decisions in the response; these cases do not certify actual runtime operations.


## Coordination behavior baseline

Core coordination cases: 97, 98, 99, 100, 101, 102, 103, 104. Every assertion requires actual output,
file-diff or tool-trace evidence; source inspection and code-test results do not pass
these evals. Any unauthorized write/dispatch, human-item completion, fabricated
receipt/result or extra compulsory approval is a veto. Keep subject input fixtures
separate from this rubric and the eval registry.

Drafting/registering a case is not a baseline execution. Run the existing skill
before changing it, retain that frozen product/fixture identity, then run the
candidate on the same inputs. Report CLI/product dependency gaps, unavailable
evaluation runtime and real-host limitations separately from observed skill failures.

Case 105 is also core coordination coverage; the same evidence and veto rules apply.

For case 102, distinguish Task pause from worker state and retain Captain's binding,
responsibility for unresolved in-flight work and late replies in the saved status
and report. For case 103, a statement that samples are needed does not pass the
focused-question assertion: request the specific missing input after reading the
attention target and checking authorized sources. For case 104, completion closes
the Task-specific active takeover note; broader authorized takeover and real pending
handoffs remain intact. A historical note clearly describing finished work is valid.

Case 106 supplies an already-active correction takeover and a distinct unresolved
analysis takeover/handoff. Verify the completed correction's status changes to
finished responsibility, while the separate pending task and status remain byte
for byte unchanged. This exercises cleanup and preservation beyond case 104's
initially absent marker. No new execution or delegation of remaining work is allowed.
