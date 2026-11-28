# Coordination and lifecycle boundaries

Product and technical design remain in the responsible parties' host workflows.
The existing route and evidence model carries delivery Tasks, dependencies,
reported pointers and attributed readiness. lb skills use those coordination
facts without inspecting design bodies or invoking a host design workflow.

## Responsibilities

Admiral owns goals and authorization. Captain plans the route with Admiral,
coordinates assignments and maintains the Logbook. Sailor performs scoped work
and returns applicable results. Captain checks completion; a runtime exit, send
receipt or bare completion claim does not prove acceptance. Additional independent
review applies when required by the confirmed route.

The CLI performs deterministic reads, validation and bounded mutations. Skills
own interpretation, sequencing, evidence applicability and recovery. A command
cannot authenticate human consent or grant business execution permission.
Switching skills does not create or revoke that permission.

| Concern | Responsible entry |
| --- | --- |
| Goal and route | `lb-plan`, `lb-scaffold` |
| Authorized advancement | `lb-push` |
| Evidence alignment and close-out | `lb-update` |
| Read-only status | `lb-status` |
| Scoped personal execution and return | `lb-takeover`, `lb-handback` |
| Reusable route templates | `lb-workflow` |
| Cross-logbook learning | `lb-retro` |

The [coordination contract](../installable/coordination.md) and
[lifecycle operations](../installable/lifecycle-operations.md) define the shared
duties. Skill entries supply their applicable decisions and recovery steps.

## Current facts and lifecycle

The Logbook carries the current route, Task states, conditions and result entries.
Bound Thinking carries material decisions, recovery information and run events;
neither document is a terminal transcript. Markdown remains authoritative under
the [storage contract](../installable/document-state.md).

Lifecycle distinguishes draft, ready, active, paused, completed and terminated.
Route readiness is separate from execution authorization. Waiting for a person
and a blocked Task are progress conditions, not separate project lifecycles.
Termination retains unfinished history and open duties without scheduling it.
Missing lifecycle evidence remains unknown.

A generated page status is a compact projection of current facts. It contains
lifecycle, a short Stage identifier where applicable and a progress qualifier.
Long Task text, counters, URLs, runtime IDs and historical narration belong in
their responsible records. Human-authored status and commentary remain protected.
Read-only status does not refresh the projection or change Task state.

## Workflow and delivery

Workflow Markdown defines reusable route content. Rendering and structural checks
do not certify semantic correctness or successful real use. Instance provenance
identifies the source template and inputs; editing a template does not alter its
existing instances. Creation, document binding and synchronization are separate
operations with explicit partial-outcome reporting.

Required delivery entries are distinct from background sources. The owning
executor checks the actual candidate and access conditions. Captain aligns those
observations with the Task; link existence or generic HTTP success alone is
insufficient. A changed candidate or entry invalidates the applicable observation.
Preserve original responsibility until a replacement and recovery path are usable.

## Metrics and learning

Run and package identities survive recovery. Timing uses observed intervals and
unions for overlapping waits; missing coverage is reported explicitly. First-pass
outcomes and later corrections retain their applicable scope. Statistics do not
invent success or introduce an extra completion gate.

Retrospective work reads a fixed authorized main-branch snapshot. It separates
finding disposition, implementation/verification and actual adoption. Keep source
occurrences in their existing records; a planned skill invocation is not usage
evidence. Snapshot coverage does not imply other branches or worktrees were read.
Retrospective proposals grant no automatic task creation or external publication.

## Runtime boundaries

Saved machine/session bindings locate execution but do not establish current
identity, exclusive ownership or delivery. Use explicit verified runtime targets
before control, preserve unknown-send guards and keep independent review distinct
from self-checks. Host directory, model and resource permissions remain effective.
See [execution records](execution-records.md) and
[observation recovery](observation-recovery-design.md) for the evidence boundaries.
