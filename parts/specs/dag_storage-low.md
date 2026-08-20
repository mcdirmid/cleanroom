# dag_storage (LLS)

## Data Types

```python
from typing import Protocol, AbstractSet, FrozenSet, Iterator, TypeVar

T = TypeVar("T")
NodeId = str  # opaque node identifier; the component does not inspect or transform it
Message = str  # a string addressed to a node

class Subgraph(AbstractSet[NodeId]):
    """A target node (included) plus all nodes reachable through its dependencies."""

class DagStorage(Protocol):
    def store_message(self, target_node: NodeId, message: Message) -> None
    def read_message(self, target_node: NodeId) -> Message
    def get_dependencies(self, target_node: NodeId) -> AbstractSet[NodeId]
    def get_reverse_dependencies(self, target_node: NodeId) -> AbstractSet[NodeId]
    def get_subgraph(self, target_node: NodeId) -> Subgraph
```

## Component-Provided Operations

### `store_message`

```python
def store_message(self, target_node: NodeId, message: Message) -> None
```

**Purpose:** Add a message to a node's message set.

**Preconditions:** The target node exists in the graph.

**Postconditions:** The message is added to the target node's message set.

**Failure Handling:** None.

**HLS Justification:** "A message enters a node" (Observable dataflow).

### `read_message`

```python
def read_message(self, target_node: NodeId) -> Message
```

**Purpose:** Remove a pending message from a node and return it.

**Preconditions:** The target node exists in the graph and has at least one pending message.

**Postconditions:** A pending message is removed from the target node's message set and returned.

**Failure Handling:** None.

**HLS Justification:** "A message is removed from a node" (Observable dataflow).

### `get_dependencies`

```python
def get_dependencies(self, target_node: NodeId) -> AbstractSet[NodeId]
```

**Purpose:** Return the dependencies of the target node.

**Preconditions:** The target node exists in the graph.

**Postconditions:** The dependencies of the target node are returned as known by the component.

**Failure Handling:** None.

**HLS Justification:** "Dependencies are provided as the component knows them" (Contract).

### `get_reverse_dependencies`

```python
def get_reverse_dependencies(self, target_node: NodeId) -> AbstractSet[NodeId]
```

**Purpose:** Return the reverse dependencies of the target node.

**Preconditions:** The target node exists in the graph.

**Postconditions:** The reverse dependencies of the target node are returned as known by the component.

**Failure Handling:** None.

**HLS Justification:** "Reverse dependencies are provided as the component knows them" (Contract).

### `get_subgraph`

```python
def get_subgraph(self, target_node: NodeId) -> Subgraph
```

**Purpose:** Return a subgraph rooted at the target node.

**Preconditions:** The target node exists in the graph.

**Postconditions:** A subgraph is returned, consisting of the target node (included) plus all nodes reachable through its dependencies.

**Failure Handling:** None.

**HLS Justification:** "A subgraph is provided" (Contract).

### `propagate_subgraph`

```python
def propagate_subgraph(self, target_node: NodeId) -> None
```

**Purpose:** When the dependencies of a node are retrieved, propagate changes to each of its propagating dependencies' reverse dependency sets, at most once per dependency.

**Preconditions:** The target node exists in the graph.

**Postconditions:** The target node's dependencies, when retrieved, are added to each of their propagating dependencies' reverse dependency sets, at most once per dependency.

**Failure Handling:** None.

**HLS Justification:** "A node's dependencies, when retrieved, are added to each of its propagating dependencies' reverse dependency sets, at most once per dependency" (Contract).

## Invariants

- A message, once read, is no longer a pending message at the target node.

## Non-Concerns

- The component's internal implementation, data structures, and performance characteristics.
