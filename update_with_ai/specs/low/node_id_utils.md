<!-- Dependencies (md files to read alongside this one):
  - dag_storage.md
-->

# Interface LLS: node_id_utils

## Data Types
```python
from typing import Protocol, TypeAlias
from dag_storage import NodeId

NodeDirectory: TypeAlias = str
RawIdentifier: TypeAlias = str
ContextIdentifier: TypeAlias = str
WorkspaceRootPath: TypeAlias = str

class NodeIdUtils(Protocol):
    def canonicalize_node_id(self, raw_id: RawIdentifier, current_context: ContextIdentifier) -> NodeId: ...
    def extract_node_directory(self, node: NodeId, workspace_root: WorkspaceRootPath) -> NodeDirectory: ...
```

- `NodeDirectory` → corresponds to *node directory*: a filesystem directory path addressing the workspace package directory of a *node*.
- `RawIdentifier` → corresponds to raw node identifier string.
- `ContextIdentifier` → corresponds to contextual node identifier string.
- `WorkspaceRootPath` → corresponds to workspace root filesystem path.
- `NodeIdUtils` → corresponds to *node identifier utility*: a service that normalizes node identifiers and resolves *node directories*.

## Term definitions

- **node directory** → the `NodeDirectory` alias
- **node identifier utility** → term definition: a service that normalizes node identifiers and resolves *node directories*.

## Component-Provided Operations

### `canonicalize_node_id`

```python
def canonicalize_node_id(self, raw_id: RawIdentifier, current_context: ContextIdentifier) -> NodeId: ...
```

**Purpose:** (NodeIdUtils) Normalizes an arbitrary string identifier into a canonical `NodeId`.

**Preconditions:**
- `raw_id` is a non-empty string.

**Postconditions:**
- Returns the canonical `NodeId` representing the target.

**Failure Handling:** Invalid identifier formats fail normalization preconditions.

**HLS Justification:** "A *node identifier utility* normalizes an arbitrary target identifier string into a canonical *node*."

### `extract_node_directory`

```python
def extract_node_directory(self, node: NodeId, workspace_root: WorkspaceRootPath) -> NodeDirectory: ...
```

**Purpose:** (NodeIdUtils) Extracts the package directory path holding the node.

**Preconditions:**
- `node` is a valid canonical `NodeId`.

**Postconditions:**
- Returns the normalized filesystem path to the node directory.

**Failure Handling:** Invalid node inputs fail preconditions.

**HLS Justification:** "A *node identifier utility* extracts a *node directory* from a *node*."

## Invariants

- Canonical node IDs produced by `canonicalize_node_id` are deterministic and stable.
- Node directory paths returned by `extract_node_directory` are normalized filesystem paths.
