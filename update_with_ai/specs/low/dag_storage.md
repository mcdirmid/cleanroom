<!-- Dependencies (md files to read alongside this one):
-->

# Interface LLS: dag_storage

## Data Types
```python
from typing import Protocol, TypeAlias, Literal
from dataclasses import dataclass

NodeId: TypeAlias = str

MessageKind: TypeAlias = Literal["change", "feedback"]

@dataclass
class NodeMessage:
    kind: MessageKind
    text: str

PendingMessages: TypeAlias = list[NodeMessage]

NodeDependencies: TypeAlias = list[NodeId]

KnownReverseDependencies: TypeAlias = list[NodeId]

class DagStorage(Protocol):
    def get_pending_messages(self, node_id: NodeId) -> PendingMessages: ...
    def add_messages(self, node_id: NodeId, messages: list[NodeMessage]) -> None: ...
    def clear_pending_messages(self, node_id: NodeId) -> None: ...
    def delete_node_data(self, node_id: NodeId) -> None: ...
    def get_node_dependencies(self, node_id: NodeId) -> NodeDependencies: ...
    def get_known_reverse_dependencies(self, node_id: NodeId) -> KnownReverseDependencies: ...
```

- `NodeMessage`: a message stored in the DAG message store — a message with a kind and text, assigned to a node by another node during cleaning. A message of kind `change` dirties the node; a message of kind `feedback` carries an obligation on the node. The store persists messages exactly as stored; kind semantics are the producer's concern, not the store's.
- `MessageKind`: the kind of a message: `"change"` or `"feedback"`.
- `NodeDependencies`: the direct dependencies of a node.
- `KnownReverseDependencies`: the nodes recorded as depending on this node.
## Term definitions

- **node** → the `NodeId` alias (definition in Data Types)
- **message** → the `NodeMessage` type (definition in Data Types)
- **message kind** → the `MessageKind` alias (definition in Data Types)
- **pending message** → the `PendingMessages` alias (definition in Data Types); term definition: a message that has been delivered to a node and has not been cleaned since delivery
- **dependency** → the `NodeDependencies` alias (definition in Data Types)
- **propagating dependency** → term definition: a dependency whose changes propagate to the depending node; only propagating dependencies record the depending node as a reverse dependency when its dependencies are retrieved
- **reverse dependency** → term definition: if a node A depends on a node B and B is a propagating dependency of A, then A is a reverse dependency of B
- **known reverse dependencies** → the `KnownReverseDependencies` alias (definition in Data Types); term definition: the nodes recorded as depending on a node — nodes that list the node among their propagating dependencies; a node becomes a known reverse dependency of each of its propagating dependencies when the node's dependencies are retrieved, a node is recorded at most once per dependency (repeated recordings do not add duplicates), and dependencies whose changes do not propagate to the node are not recorded
- **subgraph** → term definition: a target node (included) and all nodes reachable through its direct and indirect dependencies; the subgraph rooted at a node is that node and its transitive dependencies

## Component-Provided Operations

### `get_pending_messages`

```python
def get_pending_messages(self, node_id: NodeId) -> PendingMessages
```

**Purpose:** Retrieve all pending messages for a given node.

**Preconditions:** `node_id` must exist in the graph.

**Postconditions:** Provides list of pending messages (empty if none).

**Failure Handling:** No expected failures; the only caller obligation is the precondition that `node_id` exists in the graph (violations are undefined behavior). Storage failures are assumed not to occur; behavior is undefined if they do.

**HLS Justification:** "The client may read pending messages for a node."

### `add_messages`

```python
def add_messages(self, node_id: NodeId, messages: list[NodeMessage]) -> None
```

**Purpose:** Add messages to a node's pending set.

**Preconditions:** `node_id` must exist in the graph; `messages` must be valid messages.

**Postconditions:** All messages are added atomically to the node's pending set.

**Failure Handling:** No expected failures; the only caller obligations are the preconditions that `node_id` exists in the graph and `messages` are valid messages (violations are undefined behavior). Storage failures are assumed not to occur; behavior is undefined if they do.

**HLS Justification:** "The client may add messages to a node's pending set."

### `clear_pending_messages`

```python
def clear_pending_messages(self, node_id: NodeId) -> None
```

**Purpose:** Clear a node's pending messages, leaving its known reverse dependencies.

**Preconditions:** `node_id` must exist in the graph.

**Postconditions:** The node's pending messages are removed atomically; the node's known reverse dependencies remain.

**Failure Handling:** No expected failures; the only caller obligation is the precondition that `node_id` exists in the graph (violations are undefined behavior). Storage failures are assumed not to occur; behavior is undefined if they do.

**HLS Justification:** "The client may clear a node's pending messages."

### `delete_node_data`

```python
def delete_node_data(self, node_id: NodeId) -> None
```

**Purpose:** Delete a node's data: its pending messages and its known reverse dependencies.

**Preconditions:** `node_id` must exist in the graph.

**Postconditions:** The node's pending messages and known reverse dependencies are deleted atomically.

**Failure Handling:** No expected failures; the only caller obligation is the precondition that `node_id` exists in the graph (violations are undefined behavior). Storage failures are assumed not to occur; behavior is undefined if they do.

**HLS Justification:** "The client may delete a node's data (its pending messages and its known reverse dependencies)."

### `get_node_dependencies`

```python
def get_node_dependencies(self, node_id: NodeId) -> NodeDependencies
```

**Purpose:** Retrieve the direct dependencies of a node.

**Preconditions:** `node_id` must exist in the graph.

**Postconditions:**
- Provides the node's direct dependencies
- Records the node as a known reverse dependency of each propagating dependency, at most once per dependency (each propagating dependency's known reverse dependencies gain the node; repeated recordings do not duplicate it). Dependencies whose changes do not propagate to the node are not recorded.

**Failure Handling:** No expected failures; the only caller obligation is the precondition that `node_id` exists in the graph (violations are undefined behavior). Storage failures are assumed not to occur; behavior is undefined if they do.

**HLS Justification:** "The client may retrieve a node's dependencies."

### `get_known_reverse_dependencies`

```python
def get_known_reverse_dependencies(self, node_id: NodeId) -> KnownReverseDependencies
```

**Purpose:** Retrieve the nodes recorded as depending on this node.

**Preconditions:** `node_id` must exist in the graph.

**Postconditions:** Provides the node's known reverse dependencies exactly as recorded (empty if none recorded).

**Failure Handling:** No expected failures; the only caller obligation is the precondition that `node_id` exists in the graph (violations are undefined behavior). Storage failures are assumed not to occur; behavior is undefined if they do.

**HLS Justification:** "The client may retrieve a node's known reverse dependencies."


## Invariants

- Read, write, and delete operations are atomic per node.
- Messages and known reverse dependencies are provided exactly as stored and persist across restarts.


## Non-Concerns

- **Storage mechanism:** Whether messages are stored in files or a database is unspecified.
- **Serialization format:** How messages are serialized for persistence is unspecified.
- **Error handling for invalid node IDs:** Behavior when `node_id` does not exist is undefined (caller responsibility).


