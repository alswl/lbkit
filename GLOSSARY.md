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

**Observation**:
The continuing responsibility to observe a defined set of workers for a logbook and retain work that still requires attention. It survives individual listening runs.
_Avoid_: Session (ambiguous with a runtime session), monitor (a host facility)

**Event**:
An observed change in a worker that requires assessment or intervention. Delivery of its notification does not mean the intervention is complete.
_Avoid_: Acknowledgement, task result (both narrower meanings)

**Answer**:
One attempt to respond to a worker question, including whether submission and question-specific acceptance are known. A confirmed answer can resolve the associated question event.
_Avoid_: Receipt (evidence about an answer), message (does not imply a question response)
