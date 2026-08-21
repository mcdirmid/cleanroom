# dag_storage
## Dependencies: none (self-contained)

## Data Types

from typing import FrozenSet, Protocol, TypeVar

T_Node = TypeVar("T_Node")

NodeMessage = str

PendingNodeMessage = NodeMessage

ReverseDependencyNode = T_Node
Dependency = T_Node

PropagatingDependency = T_Node

Subgraph = FrozenSet[T_Node]

## Term Definitions

- **Pending message:** a message delivered to a node and not cleaned since delivery (HLS: "a message delivered to a node and not cleaned since delivery.")
- **Dependency:** A depends on B → A has an outgoing edge to B (HLS: "A depends on B -> A has an outgoing edge to B.").
- **Propagating dependency:** a dependency whose changes propagate to the depending node; retrieving a node's dependencies records the node as a reverse dependency of each of its propagating dependencies, and of no other dependency (HLS: "a dependency whose changes propagate to the depending node; retrieving a node's dependencies records the node as a reverse dependency of each of its propagating dependencies, and of no other dependency.").
- **Reverse dependency:** a node recorded as depending on another; recording happens when a node retrieves a dependency, at most once per dependency, and only for its propagating dependencies (repeated retrievals add no duplicates) (HLS: "a node recorded as depending on another; recording happens when a node retrieves a dependency, at most once per dependency, and only for its propagating dependencies (repeated retrievals add no duplicates).").
- **Subgraph:** a target node (included) plus all nodes reachable through its direct and indirect dependencies (HLS: "a target node (included) plus all nodes reachable through its direct and indirect dependencies.").

## Component-Provided Operations
class DagStorage(Protocol[T_Node]):

    def read_pending_messages(self, node: T_Node) -> FrozenSet[PendingNodeMessage]: ...
    def add_messages(self, node: T_Node, messages: FrozenSet[NodeMessage]) -> None: ...
    def delete_node(self, node: T_Node) -> None: ...
    def retrieve_dependencies(self, node: T_Node) -> FrozenSet[T_Node]: ...
    def retrieve_reverse_dependencies(self, node: T_Node) -> FrozenSet[T_Node]: ...

### `read_pending_messages`

def read_pending_messages(self, node: T_Node) -> FrozenSet[PendingNodeMessage]

**Purpose:** Read pending messages for a node.

**Preconditions:** A node exists in the graph before its messages are accessed.

**Postconditions:** The pending messages for the node are returned.

**Failure Handling:** No expected failures.

**HLS Justification:** Contract: "The client may: Read pending messages for a node." Observable dataflow: "Messages delivered to a node appear in its pending set."

### `add_messages`

def add_messages(self, node: T_Node, messages: FrozenSet[NodeMessage]) -> None

**Purpose:** Add messages to a node's pending set.

**Preconditions:** A node exists in the graph.

**Postconditions:** The messages appear in the node's pending set.

**Failure Handling:** No expected failures.

**HLS Justification:** Contract: "The client may: Add messages to a node's pending set." Observable dataflow: "Messages delivered to a node appear in its pending set."

### `delete_node`

def delete_node(self, node: T_Node) -> None

**Purpose:** Delete a node's data (its pending messages and its known reverse dependencies).

**Preconditions:** A node exists in the graph.

**Postconditions:** The node's pending messages and known reverse dependencies are removed.

**Failure Handling:** No expected failures.

**HLS Justification:** Contract: "The client may: Delete a node's data (its pending messages and its known reverse dependencies)." Observable dataflow: "Deleting a node removes its pending messages and its known reverse dependencies."

### `retrieve_dependencies`

def retrieve_dependencies(self, node: T_Node) -> FrozenSet[T_Node]

**Purpose:** Retrieve a node's dependencies.

**Preconditions:** A node exists in the graph.

**Postconditions:** The node's dependencies are returned. For each propagating dependency of the node, the node is recorded as a reverse dependency of that dependency, at most once per dependency. For non-propagating dependencies, the node is not recorded as a reverse dependency.

**Failure Handling:** No expected failures.

**HLS Justification:** Contract: "The component guarantees: Retrieving a node's dependencies records the node as a reverse dependency of each of its propagating dependencies, at most once per dependency." Observable dataflow: "Retrieving a node's dependencies records the node as a reverse dependency of each of its propagating dependencies."

### `retrieve_reverse_dependencies`

def retrieve_reverse_dependencies(self, node: T_Node) -> FrozenSet[ReverseDependencyNode]

**Purpose:** Retrieve a node's known reverse dependencies.

**Preconditions:** A node exists in the graph.

**Postconditions:** The node's known reverse dependencies are returned.

**Failure Handling:** No expected failures.

**HLS Justification:** Contract: "Retrieve a node's known reverse dependencies." Guarantees: "reverse dependencies exactly as recorded."

## Non-Concerns

- **Storage failures:** assumed not to occur; behavior is undefined if they do. (HLS Justification: Non-concerns: "Storage failures: assumed not to occur; if they do, behavior is undefined.")
## Invariants

- **Persistence:** Messages and reverse dependencies persist across component restarts. (HLS Justification: Contract: "The component guarantees: Messages and reverse dependencies persist across restarts.")
- **Atomicity:** Read, write, and delete operations are atomic per node. (HLS Justification: Contract: "The component guarantees: Read, write, and delete operations are atomic per node.")
- **Fidelity:** Messages are provided exactly as stored; dependencies as declared; reverse dependencies exactly as recorded. (HLS Justification: Contract: "The component guarantees: Messages are provided exactly as stored; dependencies as declared; reverse dependencies exactly as recorded.")
