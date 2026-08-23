<!-- Dependencies (md files to read alongside this one):
-->

# Interface LLS: dag_storage

## Data Types

```python
from __future__ import annotations

from typing import Protocol, Sequence, TypeAlias

DagNode: TypeAlias = str
NodeMessage: TypeAlias = str

class DagStorage(Protocol):
    def read_pending_messages(self, node: DagNode) -> Sequence[NodeMessage]: ...
    def add_messages(self, node: DagNode, messages: Sequence[NodeMessage]) -> None: ...
    def delete_node_data(self, node: DagNode) -> None: ...
    def get_dependencies(self, node: DagNode) -> Sequence[DagNode]: ...
    def get_reverse_dependencies(self, node: DagNode) -> Sequence[DagNode]: ...
```

The type aliases `DagNode` and `NodeMessage` correspond to the HLS terms (owned): node and message. The `DagStorage` protocol captures the dag_storage interface.

## Component-Provided Operations

Terms (cross-cutting behavioral rules):

- **pending message**: A message delivered to a node and not cleaned since delivery.
- **dependency**: A node A depends on node B means A has an outgoing edge to B.
- **propagating dependency**: A dependency whose changes propagate to the depending node; retrieving a node's dependencies records the node as a reverse dependency of each of its propagating dependencies, and of no other dependency.
- **reverse dependency**: A node recorded as depending on another; recording happens when a node retrieves a dependency, at most once per dependency, and only for its propagating dependencies (repeated retrievals add no duplicates).

### `read_pending_messages`

```python
def read_pending_messages(self, node: DagNode) -> Sequence[NodeMessage]: ...
```

**Purpose:** Retrieve all pending messages addressed to a node.

**Preconditions:** The node exists in the graph (has been declared or accessed before).

**Postconditions:** Returns the set of messages delivered to the node and not yet cleaned since delivery.

**Failure Handling:** No expected failures; storage failures are undefined per the HLS.

**HLS Justification:** "Read pending messages for a node" (Contract, Operations).

### `add_messages`

```python
def add_messages(self, node: DagNode, messages: Sequence[NodeMessage]) -> None: ...
```

**Purpose:** Add messages to a node's pending message set.

**Preconditions:** The node exists in the graph.

**Postconditions:** Each message in `messages` is appended to the node's pending set. Messages are provided exactly as stored.

**Failure Handling:** No expected failures; storage failures are undefined per the HLS.

**HLS Justification:** "Add messages to a node's pending set" (Contract, Operations).

### `delete_node_data`

```python
def delete_node_data(self, node: DagNode) -> None: ...
```

**Purpose:** Delete a node's data, including its pending messages and its known reverse dependencies.

**Preconditions:** The node exists in the graph.

**Postconditions:** The node's pending messages and known reverse dependencies are removed. The node itself (as a graph vertex) is not removed — only its associated data.

**Failure Handling:** No expected failures; storage failures are undefined per the HLS.

**HLS Justification:** "Delete a node's data (its pending messages and its known reverse dependencies)" (Contract, Operations).

### `get_dependencies`

```python
def get_dependencies(self, node: DagNode) -> Sequence[DagNode]: ...
```

**Purpose:** Retrieve a node's declared dependencies (nodes it depends on).

**Preconditions:** The node exists in the graph.

**Postconditions:** Returns the set of nodes that `node` depends on. As a side effect, for each dependency that is a *propagating dependency*, the node is recorded as a reverse dependency of that dependency (at most once per dependency, no duplicates on repeated retrievals).

**Failure Handling:** No expected failures; storage failures are undefined per the HLS.

**HLS Justification:** "Retrieve a node's dependencies" (Contract, Operations).

### `get_reverse_dependencies`

```python
def get_reverse_dependencies(self, node: DagNode) -> Sequence[DagNode]: ...
```

**Purpose:** Retrieve the node's known reverse dependencies (nodes recorded as depending on this node).

**Preconditions:** The node exists in the graph.

**Postconditions:** Returns the set of nodes recorded as reverse dependencies of this node. Reverse dependencies are recorded when a node retrieves a dependency (at most once per dependency, only for propagating dependencies).

**Failure Handling:** No expected failures; storage failures are undefined per the HLS.

**HLS Justification:** "Retrieve a node's known reverse dependencies" (Contract, Operations).

## Invariants

- Messages and reverse dependencies persist across component restarts.
- Read, write, and delete operations are atomic per node.
- Messages are provided exactly as stored; dependencies as declared; reverse dependencies exactly as recorded.
- Retrieving a node's dependencies records the node as a reverse dependency of each of its propagating dependencies, at most once per dependency.
