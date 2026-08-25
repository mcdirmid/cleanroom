<!-- Dependencies (md files to read alongside this one):
  - dag_storage.md
  - sandbox.md
-->

# Interface LLS: build_graph_storage

## Data Types
```python
from dataclasses import dataclass
from dag_storage import DagStorage, NodeId
from sandbox import SandboxConfig
from typing import Protocol, TypeAlias

GraphSource: TypeAlias = str

@dataclass
class GraphConfig:
    graph_source: GraphSource | None = None
    workspace_root: str | None = None

PackageDirectory: TypeAlias = str

@dataclass
class NodeDefinition:
    prompt: str
    sandbox_config: SandboxConfig

class BuildGraphStorage(DagStorage, Protocol):
    def resolve_node_definition(self, node_id: NodeId) -> NodeDefinition: ...
    def resolve_package_directory(self, node_id: NodeId) -> PackageDirectory: ...
```

A label identifying the configured source of graph data — either a precomputed graph artifact path or a workspace root directory. The actual resolution mechanism is unspecified.

The client-supplied configuration, as listed in the `build_graph_storage` interface contract: either a graph source or a workspace root. At least one of `graph_source` or `workspace_root` must be provided; when only the workspace root is provided, the graph is derived from it.

The directory containing a node's BUILD file; also where the node's messages are stored.

The agent prompt and sandbox configuration declared by a node's target. The sandbox configuration is a `sandbox.SandboxConfig`.

`BuildGraphStorage` fulfills the `DagStorage` Protocol — pending messages, message clearing, node dependencies, and known reverse dependencies per `dag_storage.md` — and additionally resolves node definitions and package directories.

## Term definitions

- **node definition** → the `NodeDefinition` type (definition in Data Types)
- **package directory** → the `PackageDirectory` alias (definition in Data Types)
- **silent dependency** → term definition: a dependency a node declares as silent; a silent dependency is a dependency (cleaned before the declaring node) whose changes do not propagate to the declaring node
- **star dependency** → term definition: a dependency a node declares as a star dependency; a star dependency is a dependency (cleaned before the declaring node) whose declared source, and the declared source of every node reachable from it through star dependencies (never through non-star dependencies or silent dependencies), are readable by the declaring node
- **node** → the `NodeId` alias from dag_storage
- **message** → the `NodeMessage` type from dag_storage
- **pending message** → the `PendingMessages` alias from dag_storage
- **dependency** → the `NodeDependencies` alias from dag_storage
- **propagating dependency** → term definition from dag_storage
- **reverse dependency** → term definition from dag_storage
- **subgraph** → term definition from dag_storage
- **blame target** → the `BlameTarget` alias from sandbox
- **template** → term definition from sandbox
- **guide** → term definition from sandbox
- **step mode** → term definition from sandbox

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


