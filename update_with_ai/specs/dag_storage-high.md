# dag_storage

terms (owned): node, message, pending message, dependency, propagating dependency, reverse dependency, subgraph

## Purpose

Provides persistent storage for messages addressed to nodes and access to graph topology: a node's dependencies and its known reverse dependencies. State persists across component restarts, and storage operations are atomic per node.

## Owned definitions

- Node: a vertex in the graph; messages are addressed to nodes.
- Message: a string addressed to a node.
- Pending message: a message delivered to a node and not cleaned since delivery.
- Dependency: A depends on B -> A has an outgoing edge to B.
- Propagating dependency: a dependency whose changes propagate to the depending node; retrieving a node's dependencies records the node as a reverse dependency of each of its propagating dependencies, and of no other dependency.
- Reverse dependency: a node recorded as depending on another; recording happens when a node retrieves a dependency, at most once per dependency, and only for its propagating dependencies (repeated retrievals add no duplicates).
- Subgraph: a target node (included) plus all nodes reachable through its direct and indirect dependencies.

## Observable dataflow

- Inputs: read pending messages, add messages, delete a node's data, retrieve a node's dependencies, retrieve a node's known reverse dependencies.
- Retrieving a node's dependencies records the node as a reverse dependency of each of its propagating dependencies.

## Contract

**The client may:**

- Read pending messages for a node.
- Add messages to a node's pending set.
- Delete a node's data (its pending messages and its known reverse dependencies).
- Retrieve a node's dependencies.
- Retrieve a node's known reverse dependencies.

**The component guarantees:**

- Messages and reverse dependencies persist across restarts.
- Read, write, and delete operations are atomic per node.
- Messages are provided exactly as stored; dependencies as declared; reverse dependencies exactly as recorded.
- Retrieving a node's dependencies records the node as a reverse dependency of each of its propagating dependencies, at most once per dependency.

**The component assumes:**

- A node exists in the graph before its messages, dependencies, or reverse dependencies are accessed.

## Non-concerns

- Storage failures: assumed not to occur; if they do, behavior is undefined.
