# Interface LLS: dag_storage

<!-- dependencies: (none) -->

## Data Types

```python
from typing import Protocol, TypeAlias

Node: TypeAlias = str
Message: TypeAlias = str


class DagStorage(Protocol):
    def read_pending_messages(self, node: Node) -> tuple[Message, ...]: ...
    def add_messages(self, node: Node, messages: list[Message]) -> None: ...
    def delete_node(self, node: Node) -> None: ...
    def retrieve_dependencies(self, node: Node) -> tuple[Node, ...]: ...
    def retrieve_reverse_dependencies(self, node: Node) -> tuple[Node, ...]: ...
```

- **pending message:** A message delivered to a node and not cleaned since delivery.
- **dependency:** For nodes A and B, A depends on B means A has an outgoing edge to B.
- **propagating dependency:** A dependency whose changes propagate to the depending node; only propagating dependencies trigger recording of the depending node as a reverse dependency, and of no other dependency.
- **reverse dependency:** A node recorded as depending on another node; recording happens when a node retrieves a node's dependencies, at most once per dependency, and only for its propagating dependencies (repeated retrievals add no duplicates).

## Component-Provided Operations

### `read_pending_messages`

    def read_pending_messages(self, node: Node) -> tuple[Message, ...]:

**Purpose:** Read the pending messages for a node.
**Preconditions:** The node exists in the graph before its messages are accessed.
**Postconditions:** Provides the pending messages currently associated with `node`, exactly as stored; provides an empty tuple when none are pending. Read-only: the call changes no state.
**HLS Justification:** Operations — read pending messages for a node; Guarantees — messages provided exactly as stored.

### `add_messages`

    def add_messages(self, node: Node, messages: list[Message]) -> None:

**Purpose:** Add messages to a node's pending set.
**Preconditions:** The node exists in the graph before its messages are accessed.
**Postconditions:** After the call, every message in `messages` is pending on `node`, exactly as stored. The addition persists across restarts.
**HLS Justification:** Operations — add messages to a node's pending set; Guarantees — messages provided exactly as stored; messages persist.

### `delete_node`

    def delete_node(self, node: Node) -> None:

**Purpose:** Delete a node's data (its pending messages and its known reverse dependencies).
**Preconditions:** The node exists in the graph before its messages, dependencies, or reverse dependencies are accessed.
**Postconditions:** After the call, `node`'s pending messages and its known reverse dependencies are removed.
**HLS Justification:** Operations — delete a node's data (its pending messages and its known reverse dependencies); Guarantees — messages and reverse dependencies persist.

### `retrieve_dependencies`

    def retrieve_dependencies(self, node: Node) -> tuple[Node, ...]:

**Purpose:** Retrieve a node's dependencies.
**Preconditions:** The node exists in the graph before its dependencies are accessed.
**Postconditions:** Provides the dependencies declared for `node`, exactly as declared. For each propagating dependency `d` of `node`, `node` is recorded as a reverse dependency of `d` after the call, at most once per `d` — repeated retrievals add no duplicates. Retrieval records `node` as a reverse dependency of none of its non-propagating dependencies.
**HLS Justification:** Operations — retrieve a node's dependencies; Guarantees — dependencies provided as declared; retrieval records the node as a reverse dependency of each propagating dependency, at most once per dependency.

### `retrieve_reverse_dependencies`

    def retrieve_reverse_dependencies(self, node: Node) -> tuple[Node, ...]:

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

