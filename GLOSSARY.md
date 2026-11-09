# lbkit Collaboration

Terms for observing cooperating agents and handling their requests.

## Language

**Observation**:
The continuing responsibility to observe a defined set of workers for a logbook and retain work that still requires attention. It survives individual listening runs.
_Avoid_: Session (ambiguous with a runtime session), monitor (a host facility)

**Event**:
An observed change in a worker that requires assessment or intervention. Delivery of its notification does not mean the intervention is complete.
_Avoid_: Acknowledgement, task result (both narrower meanings)

**Answer**:
One attempt to respond to a worker question, including whether submission and question-specific acceptance are known. A confirmed answer can resolve the associated question event.
_Avoid_: Receipt (evidence about an answer), message (does not imply a question response)
