<!-- Dependencies (md files to read alongside this one):
  - dag_storage.md
  - node_id_utils.md
-->

# Interface LLS: bazel_node_id_utils

## Data Types
```python
from typing import Protocol
from dag_storage import NodeId
from node_id_utils import NodeIdUtils, NodeDirectory, RawIdentifier, ContextIdentifier, WorkspaceRootPath

class BazelNodeIdUtils(NodeIdUtils, Protocol):
    def canonicalize_node_id(self, raw_id: RawIdentifier, current_context: ContextIdentifier) -> NodeId: ...
    def extract_node_directory(self, node: NodeId, workspace_root: WorkspaceRootPath) -> NodeDirectory: ...
```

- `BazelNodeIdUtils` → corresponds to *bazel node identifier utility*: a *node identifier utility* specialized for Bazel target labels and package structures.

## Term definitions

- **bazel node identifier utility** → term definition: a *node identifier utility* specialized for Bazel target labels and package structures.

## Component-Provided Operations

### `canonicalize_node_id`

```python
def canonicalize_node_id(self, raw_id: RawIdentifier, current_context: ContextIdentifier) -> NodeId: ...
```

**Purpose:** (BazelNodeIdUtils) Normalizes a raw Bazel target label into a canonical `NodeId`.

**Preconditions:**
- `raw_id` is a valid Bazel target label string.

**Postconditions:**
- Returns a canonical label starting with `//`.

**Failure Handling:** Always succeeds when preconditions are met.

**HLS Justification:** "A *bazel node identifier utility* normalizes Bazel target labels into canonical *nodes*."

### `extract_node_directory`

```python
def extract_node_directory(self, node: NodeId, workspace_root: WorkspaceRootPath) -> NodeDirectory: ...
```

**Purpose:** (BazelNodeIdUtils) Resolves the workspace package directory path for a Bazel node.

**Preconditions:**
- `node` is a canonical Bazel target label.

**Postconditions:**
- Returns the normalized filesystem path to the package directory holding the target.

**Failure Handling:** Always succeeds when preconditions are met.

**HLS Justification:** "A *bazel node identifier utility* extracts *node directories* based on Bazel package path structure."

## Invariants

- Normalizes labels according to Bazel label rules.
- Resolves package directories according to Bazel package directory rules.
