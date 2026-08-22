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

`Node` is a vertex identifier in the graph (a string). `Message` is a string addressed to a node. `PendingMessage` is a message delivered to a node and not cleaned since delivery (an alias for `Message`). `Dependency` is the declared set of nodes on which a node depends (a set of `Node` identifiers). `PropagatingDependency` is a subset of dependencies whose changes propagate to the depending node (a set of `Node` identifiers). `ReverseDependency` is the set of nodes recorded as depending on another node (a set of `Node` identifiers). `Subgraph` is a target node (included) plus all nodes reachable through its direct and indirect dependencies (a set of `Node` identifiers).

## Component-Provided Operations

### `read_pending_messages`

```python
def read_pending_messages(self, node: Node) -> set[Message]: ...
```

**Purpose:** Read all pending messages for a node.

**Preconditions:** The node exists in the graph before calling.

**Postconditions:** Returns the set of messages currently pending for the node, as stored.
**HLS Justification:** Contract → Operations: "Read pending messages for a node."

### `add_message`

```python
def add_message(self, node: Node, message: Message) -> None: ...
```

**Purpose:** Add a message to a node's pending set.

**Preconditions:** The node exists in the graph before calling.

**Postconditions:** The message is added to the node's pending set. The operation is atomic with respect to other operations on the same node.
**HLS Justification:** Contract → Operations: "Add messages to a node's pending set."

### `delete_node_data`

```python
def delete_node_data(self, node: Node) -> None: ...
```

**Purpose:** Delete all data associated with a node: its pending messages and its known reverse dependencies.

**Preconditions:** The node exists in the graph before calling.

**Postconditions:** All pending messages and all known reverse dependencies for the node are removed. The operation is atomic with respect to other operations on the same node.


**HLS Justification:** Contract → Operations: "Delete a node's data (its pending messages and its known reverse dependencies)."

### `get_dependencies`

```python
def get_dependencies(self, node: Node) -> set[Node]: ...
```

**Purpose:** Retrieve a node's declared dependencies.

**Preconditions:** The node exists in the graph before calling.

**Postconditions:** Returns the set of nodes on which the node depends (its outgoing dependency edges). Calling this operation records the node as a reverse dependency of each of its propagating dependencies, at most once per dependency. The operation is atomic with respect to other operations on the same node.

### `get_reverse_dependencies`

```python
def get_reverse_dependencies(self, node: Node) -> set[Node]: ...
```

**Purpose:** Retrieve all nodes that have recorded this node as a reverse dependency.

**Preconditions:** The node exists in the graph before calling.

**Postconditions:** Returns the set of nodes recorded as depending on (i.e., having this node as a reverse dependency). The operation is atomic with respect to other operations on the same node.


**HLS Justification:** Contract → Operations: "Retrieve a node's known reverse dependencies."

## Invariants

- **Persistence:** Messages and reverse dependencies persist across component restarts.
- **Atomicity:** Read, write, and delete operations are atomic per node.
- **Exact semantics:** Messages are provided exactly as stored; dependencies as declared; reverse dependencies exactly as recorded.

## Non-Concerns

- **Storage failures:** Assumed not to occur; if they do, behavior is undefined.
