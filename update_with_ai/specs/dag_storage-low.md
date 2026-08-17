# Interface LLS: dag_storage

## Data Types

```python
from typing import Protocol
```

```python
NodeId = str
```

```python
NodeMessage = str
```

A message stored in the DAG message store: a string assigned to a node by another node during cleaning. Produced by `dag_clean_logic`, consumed by `dag_storage`.

```python
PendingMessages = list[NodeMessage]
```

```python
NodeDependencies = list[NodeId]
```

The direct dependencies of a node.

```python
KnownReverseDependencies = list[NodeId]
```

The nodes recorded as depending on this node.

```python
class DagStorage(Protocol):
    def get_pending_messages(self, node_id: NodeId) -> PendingMessages: ...
    def add_messages(self, node_id: NodeId, messages: list[NodeMessage]) -> None: ...
    def delete_node_data(self, node_id: NodeId) -> None: ...
    def get_node_dependencies(self, node_id: NodeId) -> NodeDependencies: ...
    def get_known_reverse_dependencies(self, node_id: NodeId) -> KnownReverseDependencies: ...
```

## Term definitions

- **Subgraph**: A target node (included) and all nodes reachable through its direct and indirect dependencies. The subgraph rooted at a node is that node and its transitive dependencies.
- **Pending message**: A message that has been delivered to a node and has not been cleaned since delivery.
- **Reverse dependency**: If a node A depends on a node B, then A is a reverse dependency of B.
- **Known reverse dependencies**: The nodes recorded as depending on a node — nodes that list the node among their dependencies. A node becomes a known reverse dependency of each of its dependencies when the node's dependencies are retrieved. A node is recorded at most once per dependency; repeated recordings do not add duplicates.

## Component-Provided Operations

### `get_pending_messages`

```python
def get_pending_messages(self, node_id: NodeId) -> PendingMessages
```

**Purpose:** Retrieve all pending messages for a given node.

**Preconditions:** `node_id` must exist in the graph.

**Postconditions:** Provides list of pending messages (empty if none).


**HLS Justification:** "The client may read pending messages for a node."

### `add_messages`

```python
def add_messages(self, node_id: NodeId, messages: list[NodeMessage]) -> None
```

**Purpose:** Add messages to a node's pending set.

**Preconditions:** `node_id` must exist in the graph; `messages` must be valid messages.

**Postconditions:** All messages are added atomically to the node's pending set.


**HLS Justification:** "The client may add messages to a node's pending set."

### `delete_node_data`

```python
def delete_node_data(self, node_id: NodeId) -> None
```

**Purpose:** Delete a node's data: its pending messages and its known reverse dependencies.

**Preconditions:** `node_id` must exist in the graph.

**Postconditions:** The node's pending messages and known reverse dependencies are deleted atomically.


**HLS Justification:** "The client may delete a node's data (its pending messages and its known reverse dependencies)."

### `get_node_dependencies`

```python
def get_node_dependencies(self, node_id: NodeId) -> NodeDependencies
```

**Purpose:** Retrieve the direct dependencies of a node.

**Preconditions:** `node_id` must exist in the graph.

**Postconditions:**
- Provides the node's direct dependencies
- Records the node as a known reverse dependency of each provided dependency, at most once per dependency (each dependency's known reverse dependencies gain the node; repeated recordings do not duplicate it)


**HLS Justification:** "The client may retrieve a node's dependencies."

### `get_known_reverse_dependencies`

```python
def get_known_reverse_dependencies(self, node_id: NodeId) -> KnownReverseDependencies
```

**Purpose:** Retrieve the nodes recorded as depending on this node.

**Preconditions:** `node_id` must exist in the graph.

**Postconditions:** Provides the node's known reverse dependencies exactly as recorded (empty if none recorded).


**HLS Justification:** "The client may retrieve a node's known reverse dependencies."


## Invariants

- Read, write, and delete operations are atomic per node.
- Messages and known reverse dependencies are provided exactly as stored and persist across restarts.


## Non-Concerns

- **Storage mechanism:** Whether messages are stored in files or a database is unspecified.
- **Serialization format:** How messages are serialized for persistence is unspecified.
- **Error handling for invalid node IDs:** Behavior when `node_id` does not exist is undefined (caller responsibility).


