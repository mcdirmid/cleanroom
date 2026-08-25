<!-- Dependencies (md files to read alongside this one):
  - dag_storage-low.md
  - sandbox-low.md
-->

# Interface LLS: bazel_graph_storage

## Data Types
```python
from typing import Protocol, Sequence, TypeAlias

from dag_storage import (
    DagStorage,
    MessageContent,
    NodeName,
    PendingMessage,
    DependencyName,
    ReverseDependencyName,
)
NodeDefinition: TypeAlias = object
PackageDirectory: TypeAlias = str


class BazelGraphStorage(Protocol, DagStorage):
    def read_pending_messages(self, node: NodeName) -> Sequence[PendingMessage]: ...
    def add_messages(self, node: NodeName, messages: Sequence[MessageContent]) -> None: ...
    def delete_node(self, node: NodeName) -> None: ...
    def get_dependencies(self, node: NodeName) -> Sequence[DependencyName]: ...
    def get_reverse_dependencies(self, node: NodeName) -> Sequence[ReverseDependencyName]: ...
    def query_node_definition(self, node: NodeName) -> NodeDefinition | None: ...
    def query_package_directory(self, node: NodeName) -> PackageDirectory | None: ...
```

**BazelGraphStorage:** The interface for Bazel-workspace-backed storage and graph access, extending DagStorage with node definition and package directory queries.

**NodeDefinition:** The agent prompt and sandbox configuration declared by a node's target — file mappings, readable and writable paths, blame targets, the search result limit, the templates, and the guide.

**PackageDirectory:** The directory containing a node's BUILD file; also where the node's messages are stored.

## Term definitions

- **node** → the `NodeName` alias
- **message** → the `MessageContent` alias
- **pending message** → the `PendingMessage` alias
- **dependency** → the `DependencyName` alias
- **propagating dependency** → term definition: A dependency whose changes propagate to the depending node; when a node retrieves its dependencies, the node is recorded as a reverse dependency of each of its propagating dependencies, and of no silent dependency.
- **reverse dependency** → term definition: A node recorded as depending on another node. Recording happens when a node retrieves a dependency, at most once per dependency, and only for its propagating dependencies (repeated retrievals add no duplicates).
- **subgraph** → term definition: A target node (included) plus all nodes reachable through its direct and indirect dependencies.
- **node definition** → the `NodeDefinition` alias
- **package directory** → the `PackageDirectory` alias
- **silent dependency** → term definition: A dependency a node declares as silent; a silent dependency is a dependency (cleaned before the declaring node) whose changes do not propagate to the declaring node.
- **star dependency** → term definition: A dependency a node declares as a star dependency; a star dependency is a dependency (cleaned before the declaring node) whose declared source, and the declared source of every node reachable from it through star dependencies (never through non-star dependencies or silent dependencies), are readable by the declaring node.
- **blame target** → term definition: A dependency the agent may blame for task incompleteness (from sandbox)
- **template** → the `template` term from sandbox
- **guide** → the `guide` term from sandbox
- **step mode** → the `step mode` term from sandbox

## Component-Provided Operations

### `read_pending_messages`

```python
def read_pending_messages(self, node: NodeName) -> Sequence[PendingMessage]: ...
```

**Purpose:** Read pending messages for a node.

**Preconditions:** The node exists in the graph.

**Postconditions:** Returns all pending messages for the node, exactly as stored. The set of pending messages is unchanged. Atomic per node (see Invariants).

**Failure Handling:** None expected.

**HLS Justification:** Contract → Operations → "Perform the dag_storage operations: read pending messages." DagStorage guarantee holds.

### `add_messages`

```python
def add_messages(self, node: NodeName, messages: Sequence[MessageContent]) -> None: ...
```

**Purpose:** Add messages to a node's pending set.

**Preconditions:** The node exists in the graph.

**Postconditions:** The given messages are added to the node's pending message set. Atomic per node (see Invariants).

**Failure Handling:** None expected.

**HLS Justification:** Contract → Operations → "Perform the dag_storage operations: add messages." DagStorage guarantee holds.

### `delete_node`

```python
def delete_node(self, node: NodeName) -> None: ...
```

**Purpose:** Delete a node's data, including its pending messages and its known reverse dependencies.

**Preconditions:** The node exists in the graph.

**Postconditions:** All pending messages for the node are removed. All known reverse dependencies for the node are removed. Atomic per node (see Invariants).

**Failure Handling:** None expected.

**HLS Justification:** Contract → Operations → "Perform the dag_storage operations: delete a node's data." DagStorage guarantee holds.

### `get_dependencies`

```python
def get_dependencies(self, node: NodeName) -> Sequence[DependencyName]: ...
```

**Purpose:** Retrieve a node's dependencies.

**Preconditions:** The node exists in the graph.

**Postconditions:** Returns the node's dependencies: the targets it declares, plus the guide node, which is cleaned before the node. The guide's readable and delivery treatment follows the step-mode flag: when step mode is disabled the guide is readable; when step mode is enabled the guide is not readable and its content reaches the agent only through the advance operation. Additionally, records the node as a reverse dependency of each propagating dependency (declared dependencies excluding silent dependencies) per `Reverse dependency` and `Propagating dependency`. Atomic per node (see Invariants).

**Failure Handling:** None expected.

**HLS Justification:** Contract → Operations → "Perform the dag_storage operations: retrieve dependencies." Contract → Guarantees → dependencies include guide node with step-mode treatment; propagating dependencies exclude silent dependencies.

### `get_reverse_dependencies`

```python
def get_reverse_dependencies(self, node: NodeName) -> Sequence[ReverseDependencyName]: ...
```

**Purpose:** Retrieve a node's known reverse dependencies.

**Preconditions:** The node exists in the graph.

**Postconditions:** Returns the node's known reverse dependencies exactly as recorded. Atomic per node (see Invariants).

**Failure Handling:** None expected.

**HLS Justification:** Contract → Operations → "Perform the dag_storage operations: retrieve known reverse dependencies." DagStorage guarantee holds.

### `query_node_definition`

```python
def query_node_definition(self, node: NodeName) -> NodeDefinition | None: ...
```

**Purpose:** Query a node's definition, which includes its agent prompt, sandbox configuration, file mappings, readable and writable paths, blame targets, the search result limit, the templates, and the guide.

**Preconditions:** The node exists in the graph.

**Postconditions:** Returns the node's definition if available; returns `None` if the node has no definition. Does not modify the workspace or any state.

**Failure Handling:** Returns `None` when the node definition is not found. Signals failure without side effects when the graph source fails (the graph is unmodified).

**HLS Justification:** Contract → Operations → "Query a node's definition." Contract → Guarantees → queries do not modify the workspace; queries signal failure without side effects.

### `query_package_directory`

```python
def query_package_directory(self, node: NodeName) -> PackageDirectory | None: ...
```

**Purpose:** Query a node's package directory — the directory containing the node's BUILD file, where the node's messages are stored.

**Preconditions:** The node exists in the graph.

**Postconditions:** Returns the node's package directory if available; returns `None` if the node has no package directory. Does not modify the workspace or any state.

**Failure Handling:** Returns `None` when the node's package directory is not found. Signals failure without side effects when the graph source fails (the graph is unmodified).

**HLS Justification:** Contract → Operations → "Query a node's package directory." Contract → Guarantees → queries do not modify the workspace; queries signal failure without side effects.

## Invariants

- Messages and reverse dependencies persist across component restarts.
- All read, write, and delete operations are atomic per node.
- Queries do not modify the workspace; each query provides a consistent view of the graph.
- The dag_storage guarantees hold (as stated in the HLS).

## Non-Concerns

- **Graph-source mechanism:** how the graph is read from the configured source is unspecified. — Bounded by the HLS non-concern; the component delegates graph reading to whatever workspace-backed mechanism is configured.
- **Build execution:** the component never executes builds; it provides the graph and storage as data. — Bounded by the HLS non-concern.
