<!-- Dependencies (md files to read alongside this one):
-->

# Interface LLS: dag_storage

## Data Types
```python
from typing import Protocol, TypeAlias, Sequence, Mapping, Any, Optional
from dataclasses import dataclass

NodeId: TypeAlias = str
NodeData: TypeAlias = Mapping[str, Any]
MessageContent: TypeAlias = str

@dataclass(frozen=True)
class DagMessage:
    content: MessageContent
    sender: Optional[NodeId] = None

PendingMessage: TypeAlias = DagMessage

class DagStorage(Protocol):
    def get_dependencies(self, node: NodeId) -> Sequence[NodeId]: ...
    def get_reverse_dependencies(self, node: NodeId) -> Sequence[NodeId]: ...
    def get_pending_messages(self, node: NodeId) -> Sequence[PendingMessage]: ...
    def queue_pending_messages(self, node: NodeId, messages: Sequence[DagMessage]) -> None: ...
    def clear_pending_messages(self, node: NodeId) -> None: ...
    def record_node_data(self, node: NodeId, data: NodeData) -> None: ...
    def get_node_data(self, node: NodeId) -> Optional[NodeData]: ...
    def mark_dirty(self, node: NodeId) -> None: ...
    def is_dirty(self, node: NodeId) -> bool: ...
```

- `NodeId` → corresponds to *node*: an opaque string identifier addressing an identifiable unit of work within a *dag storage*.
- `NodeData` → corresponds to data associated with a *node*.
- `MessageContent` → corresponds to message content string.
- `DagMessage` → corresponds to *message*: a communication record passed between *nodes*.
- `PendingMessage` → corresponds to *pending message*: an unconsumed *message* queued for a *node*.
- `DagStorage` → corresponds to *dag storage*: a service that maintains a directed acyclic graph of *nodes* and their *dependencies*.

## Term definitions

- **node** → the `NodeId` alias
- **message** → the `DagMessage` alias
- **pending message** → the `PendingMessage` alias
- **dependency** → term definition: a prerequisite *node* whose completion is required before another node can be cleaned
- **propagating dependency** → term definition: a *dependency* whose changes mark dependent *nodes* dirty
- **reverse dependency** → term definition: a dependent *node* that requires the outputs of a prerequisite *node*
- **dag storage** → term definition: a service that maintains a directed acyclic graph of *nodes* and their *dependencies*

## Component-Provided Operations

### `get_dependencies`

```python
def get_dependencies(self, node: NodeId) -> Sequence[NodeId]: ...
```

**Purpose:** (DagStorage) Retrieves the prerequisite dependency nodes for a given node.

**Preconditions:**
- `node` must be a valid node in the storage graph.

**Postconditions:**
- Returns the sequence of direct dependency nodes.

**Failure Handling:** Unknown node is a caller precondition error.

**HLS Justification:** "A *dag storage* maintains *nodes*, *dependencies*, *reverse dependencies*, and *pending messages*."

### `get_reverse_dependencies`

```python
def get_reverse_dependencies(self, node: NodeId) -> Sequence[NodeId]: ...
```

**Purpose:** (DagStorage) Retrieves the dependent nodes that depend on a given node.

**Preconditions:**
- `node` must be a valid node in the storage graph.

**Postconditions:**
- Returns the sequence of direct reverse dependency nodes.

**Failure Handling:** Unknown node is a caller precondition error.

**HLS Justification:** "A *dag storage* maintains *nodes*, *dependencies*, *reverse dependencies*, and *pending messages*."

### `get_pending_messages`

```python
def get_pending_messages(self, node: NodeId) -> Sequence[PendingMessage]: ...
```

**Purpose:** (DagStorage) Retrieves all unhandled pending messages queued at a node.

**Preconditions:**
- `node` must be a valid node in the storage graph.

**Postconditions:**
- Returns the sequence of pending messages (empty if none).

**Failure Handling:** Unknown node is a caller precondition error.

**HLS Justification:** "*Pending messages* can be queued at and cleared from a *node* in a *dag storage*."

### `queue_pending_messages`

```python
def queue_pending_messages(self, node: NodeId, messages: Sequence[DagMessage]) -> None: ...
```

**Purpose:** (DagStorage) Queues new pending messages at a target node.

**Preconditions:**
- `node` must be a valid node in the storage graph.

**Postconditions:**
- DagMessages are added atomically to the node's pending message queue.

**Failure Handling:** Unknown node is a caller precondition error.

**HLS Justification:** "*Pending messages* can be queued at and cleared from a *node* in a *dag storage*."

### `clear_pending_messages`

```python
def clear_pending_messages(self, node: NodeId) -> None: ...
```

**Purpose:** (DagStorage) Clears all pending messages queued at a node.

**Preconditions:**
- `node` must be a valid node in the storage graph.

**Postconditions:**
- Removes all pending messages from the node.

**Failure Handling:** Unknown node is a caller precondition error.

**HLS Justification:** "*Pending messages* can be queued at and cleared from a *node* in a *dag storage*."

### `record_node_data`

```python
def record_node_data(self, node: NodeId, data: NodeData) -> None: ...
```

**Purpose:** (DagStorage) Associates arbitrary data or artifacts with a node.

**Preconditions:**
- `node` must be a valid node in the storage graph.

**Postconditions:**
- Persists or records data associated with the node.

**Failure Handling:** Unknown node is a caller precondition error.

**HLS Justification:** "A *dag storage* records and retrieves data associated with a *node*."

### `get_node_data`

```python
def get_node_data(self, node: NodeId) -> Optional[NodeData]: ...
```

**Purpose:** (DagStorage) Retrieves data previously associated with a node.

**Preconditions:**
- `node` must be a valid node in the storage graph.

**Postconditions:**
- Returns the recorded data, or `None` if no data has been recorded.

**Failure Handling:** Unknown node is a caller precondition error.

**HLS Justification:** "A *dag storage* records and retrieves data associated with a *node*."

### `mark_dirty`

```python
def mark_dirty(self, node: NodeId) -> None: ...
```

**Purpose:** (DagStorage) Marks a node dirty for cleaning.

**Preconditions:**
- `node` must be a valid node in the storage graph.

**Postconditions:**
- The node's state is recorded as dirty.

**Failure Handling:** Unknown node is a caller precondition error.

**HLS Justification:** "A *dag storage* marks a *node* dirty when its prerequisite in a *propagating dependency* changes."

### `is_dirty`

```python
def is_dirty(self, node: NodeId) -> bool: ...
```

**Purpose:** (DagStorage) Queries whether a node is dirty and requires cleaning.

**Preconditions:**
- `node` must be a valid node in the storage graph.

**Postconditions:**
- Returns `True` if the node is dirty, `False` otherwise.

**Failure Handling:** Unknown node is a caller precondition error.

**HLS Justification:** "A *dag storage* marks a *node* dirty when its prerequisite in a *propagating dependency* changes."

## Invariants

- Read, write, and message queue operations are atomic per node.
- Propagating dependencies ensure that changes to a prerequisite mark dependent nodes dirty.
