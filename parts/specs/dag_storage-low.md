<!-- Dependencies (md files to read alongside this one):
  -->

# Interface LLS: dag_storage

## Data Types

```python
from typing import Protocol, Sequence, TypeAlias

NodeName: TypeAlias = str
MessageContent: TypeAlias = str
PendingMessage: TypeAlias = str
DependencyName: TypeAlias = str
ReverseDependencyName: TypeAlias = str

class DagStorage(Protocol):
    def read_pending_messages(self, node: NodeName) -> Sequence[PendingMessage]: ...
    def add_messages(self, node: NodeName, messages: Sequence[MessageContent]) -> None: ...
    def delete_node(self, node: NodeName) -> None: ...
    def get_dependencies(self, node: NodeName) -> Sequence[DependencyName]: ...
    def get_reverse_dependencies(self, node: NodeName) -> Sequence[ReverseDependencyName]: ...
```

**DagStorage:** The interface for persistent storage of messages and graph topology for a DAG of nodes. Operations are atomic per node.

**NodeName:** A string identifying a vertex in the DAG graph.

**MessageContent:** A string addressed to a node.

**PendingMessage:** A message that has been delivered to a node and not yet cleaned.

**DependencyName:** A depends on B means A has an outgoing edge to B.

**ReverseDependencyName:** A node recorded as depending on another node.


## Term definitions

- **node** → the `NodeName` alias
- **message** → the `MessageContent` alias
- **pending message** → the `PendingMessage` alias
- **dependency** → the `DependencyName` alias
- **propagating dependency** → term definition: A dependency whose changes propagate to the depending node; when a node retrieves its dependencies, the node is recorded as a reverse dependency of each of its propagating dependencies, and of no other dependency.
- **reverse dependency** → term definition: A node recorded as depending on another node. Recording happens when a node retrieves a dependency, at most once per dependency, and only for its propagating dependencies (repeated retrievals add no duplicates).
- **subgraph** → term definition: A target node (included) plus all nodes reachable through its direct and indirect dependencies.

## Component-Provided Operations

### `read_pending_messages`

```python
def read_pending_messages(self, node: NodeName) -> Sequence[PendingMessage]: ...
```

**Purpose:** Read pending messages for a node.

**Preconditions:** The node exists in the graph.

**Postconditions:** Returns all pending messages for the node, exactly as stored. The set of pending messages is unchanged. Atomic per node (see Invariants).

**Failure Handling:** None expected.

**HLS Justification:** Contract — "Read pending messages for a node."

### `add_messages`

```python
def add_messages(self, node: NodeName, messages: Sequence[MessageContent]) -> None: ...
```

**Purpose:** Add messages to a node's pending set.

**Preconditions:** The node exists in the graph.

**Postconditions:** The given messages are added to the node's pending message set. Atomic per node (see Invariants).

**Failure Handling:** None expected.

**HLS Justification:** Contract — "Add messages to a node's pending set."

### `delete_node`

```python
def delete_node(self, node: NodeName) -> None: ...
```

**Purpose:** Delete a node's data, including its pending messages and its known reverse dependencies.

**Preconditions:** The node exists in the graph.

**Postconditions:** All pending messages for the node are removed. All known reverse dependencies for the node are removed. Atomic per node (see Invariants).

**Failure Handling:** None expected.

**HLS Justification:** Contract — "Delete a node's data (its pending messages and its known reverse dependencies)."

### `get_dependencies`

```python
def get_dependencies(self, node: NodeName) -> Sequence[DependencyName]: ...
```

**Purpose:** Retrieve a node's dependencies.

**Preconditions:** The node exists in the graph.

**Postconditions:** Returns the node's dependencies exactly as declared. Additionally, records the node as a reverse dependency of each propagating dependency per `Reverse dependency` and `Propagating dependency`. Atomic per node (see Invariants).

**Failure Handling:** None expected.

**HLS Justification:** Contract — "Retrieve a node's dependencies" and "Retrieving a node's dependencies records the node as a reverse dependency of each of its propagating dependencies, at most once per dependency."

### `get_reverse_dependencies`

```python
def get_reverse_dependencies(self, node: NodeName) -> Sequence[ReverseDependencyName]: ...
```

**Purpose:** Retrieve a node's known reverse dependencies.

**Preconditions:** The node exists in the graph.

**Postconditions:** Returns the node's known reverse dependencies exactly as recorded. Atomic per node (see Invariants).

**Failure Handling:** None expected.

**HLS Justification:** Contract — "Retrieve a node's known reverse dependencies."

## Invariants
- Messages and reverse dependencies persist across component restarts.
- All read, write, and delete operations are atomic per node.

## Non-Concerns
- **Storage failures:** assumed not to occur — behavior is undefined if they do.
