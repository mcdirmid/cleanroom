<!-- Dependencies (md files to read alongside this one):
  - dag_storage.md
  - build_graph_storage.md
  - sandbox.md
  - run_control.md
  - file_reader.md
  - file_editor.md
  - guide_delivery.md
-->

# Interface LLS: manifest_node_loader

## Data Types
```python
from typing import Dict, List, Optional, Protocol, Tuple, TypeAlias
from dataclasses import dataclass
from build_graph_storage import NodeDefinition, PackageDirectory, GraphConfig
from dag_storage import NodeId, NodeDependencies

@dataclass
class LoadedGraphManifests:
    node_definitions: Dict[NodeId, NodeDefinition]
    node_dependencies: Dict[NodeId, NodeDependencies]
    package_directories: Dict[NodeId, PackageDirectory]
    propagating_dependencies: Dict[NodeId, NodeDependencies]
    silent_dependencies: Dict[NodeId, NodeDependencies]

class ManifestNodeLoader(Protocol):
    def resolve_graph(self, config: GraphConfig) -> LoadedGraphManifests: ...
```

## Term definitions

- **manifest resolution** → term definition: the process of reading JSON manifest files from a workspace directory and resolving all dependency edges and file paths
- **synthetic definition** → term definition: a generated node definition for a declared dependency that lacks a build manifest of its own
- **node definition** → the `NodeDefinition` dataclass from build_graph_storage
- **package directory** → the `PackageDirectory` alias from build_graph_storage
- **silent dependency** → term definition from build_graph_storage
- **star dependency** → term definition from build_graph_storage
- **blame target** → the `BlameTarget` alias from run_control
- **virtual name** → the `VirtualName` alias from file_reader
- **template** → the `TemplateMapping` alias from file_editor
- **guide** → term definition from guide_delivery
- **step mode** → term definition from guide_delivery
- **node** → the `NodeId` alias from dag_storage
- **dependency** → the `NodeDependencies` alias from dag_storage
- **propagating dependency** → term definition from dag_storage

## Component-Provided Operations

### `resolve_graph`

```python
def resolve_graph(self, config: GraphConfig) -> LoadedGraphManifests
```

**Purpose:** Scan and resolve manifests for a workspace graph starting from the configured root label.

**Preconditions:**
- `config` specifies a valid workspace root and root node label.

**Postconditions:**
- Returns `LoadedGraphManifests` containing node definitions, package directories, and dependency sets for all reachable nodes.

**Failure Handling:** Missing manifests for external dependencies synthesize fallback node definitions.

**HLS Justification:** "Resolve the full dependency graph and per-node definitions starting from a root target."

## Invariants

- All reachable nodes have resolved package directories and definitions.
- Star dependencies are transitively closed over star relationships only.

## Non-Concerns

- Runtime message mutations: handled by build_message_store and build_graph_storage_impl.
