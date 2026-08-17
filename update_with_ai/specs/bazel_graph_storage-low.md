<!-- Dependencies (md files to read alongside this one):
  - dag_storage-low.md
  - sandbox-low.md
-->

# Interface LLS: bazel_graph_storage

## Data Types

```python
from dataclasses import dataclass
from dag_storage import DagStorage, NodeId
from sandbox import SandboxConfig
from typing import Protocol
```

```python
GraphSource = str
```

A label identifying the configured source of graph data — either a precomputed graph artifact path or a workspace root directory. The actual resolution mechanism is unspecified; the implementation determines how to read the graph from the source.

```python
@dataclass
class GraphConfig:
    graph_source: GraphSource | None = None
    workspace_root: str | None = None
```

The client-supplied configuration, as listed in the `bazel_graph_storage` interface contract: either a graph source or a workspace root. At least one of `graph_source` or `workspace_root` must be provided; when only the workspace root is provided, the graph is derived from it.

```python
PackageDirectory = str
```

The directory containing a node's BUILD file; also where the node's messages are stored.

```python
@dataclass
class NodeDefinition:
    prompt: str
    sandbox_config: SandboxConfig
```

The agent prompt and sandbox configuration declared by a node's target. The sandbox configuration is a `sandbox.SandboxConfig`.

```python
class BazelGraphStorage(DagStorage, Protocol):
    def resolve_node_definition(self, node_id: NodeId) -> NodeDefinition: ...
    def resolve_package_directory(self, node_id: NodeId) -> PackageDirectory: ...
```

`BazelGraphStorage` fulfills the `DagStorage` Protocol — pending messages, node dependencies, and known reverse dependencies per `dag_storage-low.md` — and additionally resolves node definitions and package directories.

## Component-Provided Operations

### `resolve_node_definition`

```python
def resolve_node_definition(self, node_id: NodeId) -> NodeDefinition
```

**Purpose:** Return the agent prompt and sandbox configuration declared by a node's target.

**Preconditions:**
- `node_id` is a valid Bazel target label
- The node ID resolves to a target with a complete definition

**Postconditions:**
- Returns a `NodeDefinition` containing the node's agent prompt and sandbox configuration as declared by the target

**Failure Handling:**
- No expected failure conditions other than graph-source failures, which signal failure without side effects (see Invariants). The only caller obligation is the precondition: `node_id` is a valid Bazel target label. Violations are unexpected; the interface does not prescribe violation behavior.

**HLS Justification:** "Query a node's definition (the agent prompt and sandbox configuration)."


### `resolve_package_directory`

```python
def resolve_package_directory(self, node_id: NodeId) -> PackageDirectory
```

**Purpose:** Return the directory containing the node's BUILD file.

**Preconditions:**
- `node_id` is a valid Bazel target label

**Postconditions:**
- Returns the package directory as the directory containing the node's BUILD file
- Also the directory where the node's messages are stored

**Failure Handling:**
- No expected failure conditions other than graph-source failures, which signal failure without side effects (see Invariants). The only caller obligation is the precondition: `node_id` is a valid Bazel target label. Violations are unexpected; the interface does not prescribe violation behavior.

**HLS Justification:** "Query a node's package directory."


## Invariants

- Queries are read-only; no workspace modification occurs
- Each query provides a consistent view of the graph
- Graph-source failures signal failure without side effects
- The graph topology is acyclic (an assumption; verification is not specified)


## Non-Concerns

- **Graph-source mechanism:** How the graph is read from the configured source is unspecified.


