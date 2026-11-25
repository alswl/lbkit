# lbkit Collaboration

Terms for observing cooperating agents and handling their requests.

## Language

**Task（任务）**:
A unit of planned work with its own acceptance criteria and current responsibility.

**Sailor**:
The collaborating agent responsible for executing an accepted work instruction and returning its results.
_Avoid_: Pane, tab, Herdr agent (execution resources or backend-specific identities)

**Delegation**:
Entrusting an authorized work instruction to a Sailor, with responsibility for its acceptance and returned results.
_Avoid_: Resource creation, message delivery (neither alone establishes delegation)

**Collaboration adapter**:
A concrete means of interacting with Sailors through an execution environment. The Sailor role and delegation responsibility are independent of the chosen adapter.
_Avoid_: Sailor (the executing role), runtime (the agent's execution engine)

**Task responsibility**:
The current Human or Agent assigned to a Task. Admiral/Captain/Sailor describe
logical roles; Human/Agent describe engineering subjects. Assignment alone does
not start work, stop old work or authorize runtime control.

**Handoff（交回）**:
The transfer of responsibility for remaining work from the current owner to an
authorized recipient whose acceptance and readiness have been verified.

**Execution binding**:
An immutable snapshot locating a Task's actual subject, machine, native session,
repository/work directory and instruction input. A Task can retain historical
bindings; its current binding is only a reference.

**Preflight（预检）**:
Preparation for planned work that checks applicable prerequisites and records current evidence and gaps. It operates within existing authorization.

**Seat Requirement（席位需求）**:
A prerequisite in a route that calls for a Sailor to support one or more Tasks.
It can exist before a Sailor is selected or assigned responsibility for a Task.

**Self-Check Request（自检请求）**:
A request for a selected Sailor to check a prerequisite in the intended execution environment.

**Self-Check Evidence（自检证据）**:
A Sailor's attributable result for a specific Self-Check Request and execution environment.

**Document projection**:
Rebuildable structured data generated explicitly from Markdown by sync-state.
Markdown is the document SSOT; execution and monitoring facts are independent.

**Monitoring**:
An internal capability for observing native sessions and retaining unresolved
events and answers. Empty targets are valid. It is not a separate business object.

**Event**:
An observed change in a worker that requires assessment or intervention. Delivery of its notification does not mean the intervention is complete.
_Avoid_: Acknowledgement, task result (both narrower meanings)

**Answer**:
One attempt to respond to a worker question, including whether submission and question-specific acceptance are known. A confirmed answer can resolve the associated question event.
_Avoid_: Receipt (evidence about an answer), message (does not imply a question response)
