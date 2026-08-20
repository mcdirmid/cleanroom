# dag_storage

terms (owned): node, message, pending message, dependency, propagating dependency, reverse dependency, subgraph

## Purpose

Provides storage for messages addressed to nodes and access to graph topology: a node's dependencies and its known reverse dependencies.

## Owned definitions

- Node: an opaque vertex in the graph.
- Message: a string addressed to a node.
- Pending message: a message present at a node since its last read.
- Dependency: a node depends on another node; the depended-upon node is the dependency, distinguished by the relationship not by its identity.
- Propagating dependency: a dependency whose changes propagate to the depending node; or custom conditions hold.
- Reverse dependency: a node that depends on another node; the component may provide reverse dependencies for nodes that do not depend on the requesting node, and for nodes whose dependencies include the requesting node; the exact set of nodes the component tracks is unspecified, and the component does not expose which nodes it tracks.
- Subgraph: a target node (included) plus all nodes reachable through its dependencies.

## Observable dataflow

A message enters a node.
A message is removed from a node.

## Contract

**The client may:**

**The component guarantees:**

- Messages are provided exactly as stored.
- Dependencies are provided as the component knows them.
- Reverse dependencies are provided as the component knows them.
- A node's dependencies, when retrieved, are added to each of its propagating dependencies' reverse dependency sets, at most once per dependency.

**The component assumes:**
- A node exists in the graph before its messages, dependencies, or reverse dependencies are accessed.

## Non-concerns

- The component's internal implementation, data structures, and performance characteristics.
