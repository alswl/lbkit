# Coordination Roles and Contracts

The human owner holds goals, risk acceptance, and irreversible decisions; the coordinator of each logbook maintains shared state, dependencies, and acceptance; executor agents deliver bounded work packages. The permission floor is defined by [AGENTS.md](../AGENTS.md); concrete operation order is constrained by the lb-* skills.

## Scope, Authorization, and Dependencies

Plan confirmation is not execution authorization. A "push the project forward" request, or an lb-push request not scoped to a single item, authorizes serial progress along the confirmed path until completion, a human gate, or a severe blocker; "finish just this one", "start the next item", or an explicit batch honors the specified endpoints. Requests for analysis only, formatting only, or status only grant no permission to start. Existing authorization remains valid within its scope; items are not re-confirmed one by one.

Stages explicitly owned by other coordinators keep their scheduling ownership; sharing a logbook or hearing about progress does not confer the right to take over. Split-off stages keep the original owner, and handoff notices are kept separate from dispatching project tasks.

Cross-item parallelism requires explicit batch authorization, plus stable inputs, satisfied dependencies, and non-overlapping mutable resources. The first item blocking, the second being more urgent, or an extra agent helping are none of them grounds to skip, reorder, or widen scope.

Investigation, inspection, and limited rework within the original work package fall inside the original authorization. Missing information is filled in by the owning agent within the authorization; out-of-scope questions go to the human. Deviations from the confirmed plan can be corrected; when the plan itself is heading the wrong way or a major decision is involved, stop and hand over to the human. Timeouts and recovery follow the [execution flow](../skills/lb-push/references/execution.md).

Agents may draft todos and write them in after confirmation; additions, reordering, and widened task scope still require confirmation. An existing list plus authorization to proceed is enough to prepare the next execution work package — do not repeatedly ask for approval over work-package wording. Operations by the same owner delivering the same result are not split into items; when the owner or the acceptance gate changes, split into sequential tasks, and do not parallelize on that basis.

When asking a human for an on-the-spot ruling, use a compact numbered list: number each item, give candidates and a default recommendation, so the human can answer by number in one line; no long paragraphs. Collect multiple rulings in one round instead of interrupting item by item.

Git commit discipline for coordinators: when working in the same repository as a human, always commit with `git commit -- <explicit path>` (pathspec) and self-check with `show --stat` afterwards to confirm no one else's files slipped in; committing without a pathspec sweeps up the human's staged in-flight content. The reverse trap is just as real: when the same file mixes in uncommitted lines from the owner, a pathspec commit takes the entire **working tree** version, dragging the owner's lines into the commit and afterwards writing back over the manually staged index. When you need to commit only your own lines, do index surgery: `git hash-object -w <sanitized content>` plus `git update-index --cacheinfo 100644 <blob> <path>` to stage precisely, then run `git commit` **without a pathspec** so the commit tree comes only from the index; afterwards use `git status` to confirm the owner's lines are still in the working tree. Before and after rewriting or repairing local history, `fetch` first and check the remote state of the target branch; never assert from session memory that "the remote doesn't have this branch / it was never pushed" — the remote may already have a same-name branch or a push made in the meantime, and missing it causes divergence.

## Work Packages and Return Fields

The [work package template](../skills/lb-plan/assets/work-package.md) is an execution contract, not a second scheduling checklist. It links to the result in the main logbook and contains at least:

- 所属检查项 (owning checklist item), one owner, and one provable result;
- Scope, explicit exclusions, inputs, and authoritative sources;
- Dependencies, parallelism boundaries, authorization basis, and permitted operations;
- Deliverable location, immutable identity, and raw evidence format;
- Completion conditions, required checkers and pass criteria, and a limited number of review rounds;
- Blocking and escalation conditions, handoff responsibilities, and session retention or closure conditions.

A return includes status, delivered result, candidate identity, evidence, remaining gaps, blocker category, affected acceptance gates, and open responsibilities. "Keep investigating" and "help the project" are not complete work packages.

When the PR a work package is expected to produce mixes several kinds of changes (prerequisite non-project, docs, code implementation) or is clearly larger than usual, split it into sequential small PRs — prerequisite non-project → docs → code implementation — so a single giant PR does not jam human review.

Until a human owner explicitly answers an inquiry, do not widen that inquiry's discretion by inferring intent — ask again for an explicit ruling rather than making a downstream-costly decision on the human owner's behalf.

When a short instruction has multiple readings (e.g. "watch the error message" could mean finding the root cause or rewording the copy), reply with a one-line semantic confirmation before dispatching the package; do not guess a direction and build a full work package on it.

This run's choices are resolved per the [configuration contract](configuration.md); the work package records only the parameters actually needed and their sources, not a copy of the whole default configuration. Distinguish missing fields from inapplicable ones; tasks that need no independent review must not get checkers created just to fill the round count.

## Design Sources

The following are design references, not mandatory flows:

- [Anthropic: Building effective agents](https://www.anthropic.com/research/building-effective-agents): dynamic decomposition and independent subtasks.
- [Anthropic: multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system): task boundaries and outputs.
- [OpenAI Agents SDK: orchestration](https://openai.github.io/openai-agents-python/multi_agent/): manager aggregation and specialist division of labor.
- [Azure: orchestration patterns](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/ai-agent-design-patterns): minimal necessary complexity and limited review rounds.
