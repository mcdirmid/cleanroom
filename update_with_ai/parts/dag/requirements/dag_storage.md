# dag_storage interface component

## Assumptions and Requirements

### Requirements

1. A unit is an end-artifact that is being worked on.
2. A role describes a phase of work being done to an artifact.
3. A node identifies a discrete unit of work in the graph, having a unit address and a role address.
4. A dag storage stores node graph structure, status, and messages.
5. Providing access to a node's dependencies returns its direct upstream nodes in the graph and identifies whether each dependency is silent to preclude change message propagation from that dependency.
6. Registering a node as a dependent adds the node to the dependents of all of its non-silent dependencies.
7. Accessing dependents registered to a node returns the downstream nodes registered as dependents for that node.
8. Clearing the dependents registered to a node removes all recorded dependents for that node.
9. A message is text content explaining to the agent why a node requires cleaning, and is either a change message informing of changes made to upstream dependencies, or a feedback message blaming a specific dependency target node for defects detected by downstream dependents.
10. Adding a message to a node records the message for that node.
11. Accessing messages for a node returns all recorded messages for that node.
12. Clearing messages from a node removes all recorded messages for that node.
13. Exposing whether a node is dirty returns true if the node has messages.

## Grounding Facts

### Knowledge Needed

- Node identity (unit address and role address).
- Upstream dependencies and silent dependency flags.
- Downstream dependents registration.
- Change messages and feedback messages.
- Dirty status based on message presence.

### Actions Needed

- Query node dependencies and silent flags.
- Register, retrieve, and clear node dependents.
- Record, retrieve, and clear node messages.
- Evaluate node dirty status.
