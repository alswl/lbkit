# lbkit Collaboration

Terms for observing cooperating agents and handling their requests.

## Language

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

**Execution binding**:
An immutable snapshot locating a Task's actual subject, machine, native session,
repository/work directory and instruction input. A Task can retain historical
bindings; its current binding is only a reference.

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
