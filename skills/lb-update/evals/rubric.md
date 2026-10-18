# lb-update behavior rubric

Apply the shared [evaluation method](../../../docs/dev/development.md#behavior-evaluation).
Case inputs and assertions live in [evals.json](evals.json).

Hard vetoes: unauthorized dispatch/write; Captain performing concrete business acceptance; completing human items; overwriting unsaved human input; inventing acceptance or receipt; creating TODO.md or a replacement compulsory archive. Any veto fails the case.

Core cases: 10, 18, 44–47. Every assertion must pass under the shared evidence rules.

Case 44 checks repair through the owning Sailor; case 47 checks update-only refusal of an incomplete delivery. Neither permits Captain to perform business acceptance.

Cases 48–49 are also core: require actual tool/file evidence for every assertion. A written scenario or static rule audit alone is not a behavioral PASS.

Cases 50–51 are core paired local progress scenarios: reject incomplete returns and accept sufficient scoped returns. Case 50 requires an actionable owning-return note in the actual delivery task, not only a chat warning. Case 51 prevents a refusal-only implementation from passing. These fixtures do not establish live PR or remote execution coverage.
