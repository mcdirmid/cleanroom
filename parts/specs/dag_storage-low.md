# Interface LLS: dag_storage

<!-- dependencies: (none) -->

## Data Types

```python
from typing import Protocol, TypeAlias

Node: TypeAlias = str
Message: TypeAlias = str
PendingMessage: TypeAlias = str
Dependency: TypeAlias = str
PropagatingDependency: TypeAlias = Dependency
ReverseDependency: TypeAlias = str
Subgraph: TypeAlias = set[Node]

class DagStorage(Protocol):
    def read_pending_messages(self, node: Node) -> tuple[PendingMessage, ...]: ...
    def add_messages(self, node: Node, messages: list[Message]) -> None: ...
    def delete_node(self, node: Node) -> None: ...
    def retrieve_dependencies(self, node: Node) -> tuple[Dependency, ...]: ...
    def retrieve_reverse_dependencies(self, node: Node) -> tuple[ReverseDependency, ...]: ...
```

- `Node`: A vertex in the graph; messages are addressed to nodes.
- `Message`: A string addressed to a node.
- `PendingMessage`: A message delivered to a node and not cleaned since delivery.
- `Dependency`: A node that the current node depends on; A depends on B means A has an outgoing edge to B.
- `PropagatingDependency`: A dependency whose changes propagate to the depending node.
- `ReverseDependency`: A node recorded as depending on another.
- `Subgraph`: A target node (included) plus all nodes reachable through its direct and indirect dependencies.

## Component-Provided Operations

### `read_pending_messages`

    def read_pending_messages(self, node: Node) -> tuple[PendingMessage, ...]:

**Purpose:** Read the pending messages for a node.
**Preconditions:** The node exists in the graph before its messages are accessed.
**Postconditions:** Provides the pending messages currently associated with `node`, exactly as stored; provides an empty tuple when none are pending. Read-only: the call changes no state.
**HLS Justification:** Operations — read pending messages for a node; Guarantees — messages provided exactly as stored.

### `add_messages`

    def add_messages(self, node: Node, messages: list[Message]) -> None:

**Purpose:** Add messages to a node's pending set.
**Preconditions:** The node exists in the graph before its messages are accessed.
**Postconditions:** After the call, every message in `messages` is pending on `node`, exactly as stored. The addition persists across restarts and the operation is atomic per node.
**HLS Justification:** Operations — add messages to a node's pending set; Guarantees — messages provided exactly as stored; messages persist; operations atomic per node.

### `delete_node`

    def delete_node(self, node: Node) -> None:

**Purpose:** Delete a node's data (its pending messages and its known reverse dependencies).
**Preconditions:** The node exists in the graph before its messages, dependencies, or reverse dependencies are accessed.
**Postconditions:** After the call, `node`'s pending messages and its known reverse dependencies are removed, persistently across restarts. The operation is atomic per node.
**HLS Justification:** Operations — delete a node's data (its pending messages and its known reverse dependencies); Guarantees — messages and reverse dependencies persist; operations atomic per node.

### `retrieve_dependencies`

    def retrieve_dependencies(self, node: Node) -> tuple[Dependency, ...]:

**Purpose:** Retrieve a node's dependencies.
**Preconditions:** The node exists in the graph before its dependencies are accessed.
**Postconditions:** Provides the dependencies declared for `node`, exactly as declared. For each propagating dependency `d` of `node`, `node` is recorded as a reverse dependency of `d` after the call, at most once per `d` — repeated retrievals add no duplicates. Retrieval records `node` as a reverse dependency of none of its non-propagating dependencies.
**HLS Justification:** Operations — retrieve a node's dependencies; Guarantees — dependencies provided as declared; retrieval records the node as a reverse dependency of each propagating dependency, at most once per dependency.

### `retrieve_reverse_dependencies`

    def retrieve_reverse_dependencies(self, node: Node) -> tuple[ReverseDependency, ...]:

**Purpose:** Retrieve a node's known reverse dependencies.
**Preconditions:** The node exists in the graph before its reverse dependencies are accessed.
**Postconditions:** Provides the nodes currently recorded as reverse dependencies of `node`, exactly as recorded. Read-only: the call changes no state.
**HLS Justification:** Operations — retrieve a node's known reverse dependencies; Guarantees — reverse dependencies provided exactly as recorded.

## Invariants

- Messages and reverse dependencies persist across component restarts.
- Read, write, and delete operations are atomic per node.

## Non-concerns

- **Storage failures:** Assumed not to occur; if they do, behavior is undefined — no error handling defined.
- **Graph topology management:** The graph is assumed to exist before access; creating or modifying nodes and their declared dependencies is out of scope for this component.
- **Subgraph computation:** The `Subgraph` concept is defined for use by consumers; computing subgraphs is not an operation of this component.
- **Message ordering within the pending set:** Not specified; clients may not rely on ordering.
- **Cleanup of pending messages:** Not specified; out of scope for this component.

