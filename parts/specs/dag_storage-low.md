# Interface LLS: dag_storage
## Data Types

```python
from typing import TypeAlias

Node: TypeAlias = str
Message: TypeAlias = str
PendingMessage: TypeAlias = Message
Dependency: TypeAlias = Node
PropagatingDependency: TypeAlias = Node
ReverseDependency: TypeAlias = Node
Subgraph: TypeAlias = frozenset[Node]


class dag_storage(Protocol):
    def read_pending_messages(self, node: Node) -> set[Message]: ...
    def add_message(self, node: Node, message: Message) -> None: ...
    def delete_node_data(self, node: Node) -> None: ...
    def get_dependencies(self, node: Node) -> set[Node]: ...
    def get_reverse_dependencies(self, node: Node) -> set[Node]: ...
```

`Node` is a vertex identifier in the graph (a string). `Message` is a string addressed to a node. `PendingMessage` is a message delivered to a node and not cleaned since delivery (an alias for `Message`). `Dependency` is a node on which another node depends (a single `Node` identifier). `PropagatingDependency` is a dependency whose changes propagate to the depending node; retrieving a node's dependencies records the node as a reverse dependency of each of its propagating dependencies, and of no other dependency (a single `Node` identifier). `ReverseDependency` is a node recorded as depending on another node (a single `Node` identifier; recording happens when a node retrieves a dependency, at most once per dependency, and only for its propagating dependencies). `Subgraph` is a target node (included) plus all nodes reachable through its direct and indirect dependencies (a frozenset of `Node` identifiers).

## Component-Provided Operations

### `read_pending_messages`

```python
def read_pending_messages(self, node: Node) -> set[Message]: ...
```

**Purpose:** Read all pending messages for a node.

**Preconditions:** The node exists in the graph before calling.

**Postconditions:** Returns the set of messages currently pending for the node, as stored. The operation is atomic with respect to other operations on the same node.
**Failure Handling:** No failures defined in HLS.
**HLS Justification:** Contract → Operations: "Read pending messages for a node."

### `add_message`

```python
def add_message(self, node: Node, message: Message) -> None: ...
```

**Purpose:** Add a message to a node's pending set.

**Preconditions:** The node exists in the graph before calling.

**Postconditions:** The message is added to the node's pending set. The operation is atomic with respect to other operations on the same node.

**Failure Handling:** No failures defined in HLS.

**HLS Justification:** Contract → Operations: "Add messages to a node's pending set."

### `delete_node_data`

```python
def delete_node_data(self, node: Node) -> None: ...
```

**Purpose:** Delete all data associated with a node: its pending messages and its known reverse dependencies.

**Preconditions:** The node exists in the graph before calling.

**Postconditions:** All pending messages and all known reverse dependencies for the node are removed. The operation is atomic with respect to other operations on the same node.

**Failure Handling:** No failures defined in HLS.

**HLS Justification:** Contract → Operations: "Delete a node's data (its pending messages and its known reverse dependencies)."

### `get_dependencies`

```python
def get_dependencies(self, node: Node) -> set[Node]: ...
```

**Purpose:** Retrieve a node's declared dependencies.

**Postconditions:** Returns the set of nodes on which the node depends. Retrieving dependencies records the calling node as a reverse dependency of each of its propagating dependencies (at most once per dependency). The operation is atomic with respect to other operations on the same node.

**Failure Handling:** No failures defined in HLS.

**HLS Justification:** Contract → Operations: "Retrieve a node's dependencies."

### `get_reverse_dependencies`

```python
def get_reverse_dependencies(self, node: Node) -> set[Node]: ...
```

**Purpose:** Retrieve all nodes that have recorded this node as a reverse dependency.

**Preconditions:** The node exists in the graph before calling.

**Postconditions:** Returns the set of nodes recorded as depending on (i.e., having this node as a reverse dependency). The operation is atomic with respect to other operations on the same node.

**Failure Handling:** No failures defined in HLS.

**HLS Justification:** Contract → Operations: "Retrieve a node's known reverse dependencies."

## Invariants

- **Persistence:** Messages and reverse dependencies persist across component restarts.
- **Atomicity:** Read, write, and delete operations are atomic per node.
- **Exact semantics:** Messages are provided exactly as stored; dependencies as declared; reverse dependencies exactly as recorded.

## Non-Concerns

- **Storage failures:** Assumed not to occur; if they do, behavior is undefined.
