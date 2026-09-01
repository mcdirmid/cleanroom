<!-- Dependencies (md files to read alongside this one):
  - dag_storage.md
  - node_id_utils.md
-->

# Interface LLS: build_message_store

## Data Types
```python
from typing import Protocol
from dag_storage import DagStorage, NodeId
from node_id_utils import NodeDirectory

class BuildMessageStore(DagStorage, Protocol):
    def get_package_directory(self, node: NodeId) -> NodeDirectory: ...
```

- `BuildMessageStore` → corresponds to *build message store*: a *dag storage* persistence layer storing node message data in package directories.

## Term definitions

- **build message store** → term definition: a *dag storage* persistence layer storing node message data in package directories
- **node directory** → the `NodeDirectory` alias from node_id_utils

## Component-Provided Operations

### `get_package_directory`

```python
def get_package_directory(self, node: NodeId) -> NodeDirectory: ...
```

**Purpose:** (BuildMessageStore) Resolves the workspace package directory path for a node.

**Preconditions:**
- `node` is a valid node in the storage graph.

**Postconditions:**
- Returns the filesystem path to the package directory holding the node.

**Failure Handling:** Always succeeds when preconditions are met.

**HLS Justification:** "A *build message store* reads and writes *pending messages* and *reverse dependencies* for *nodes* in their package *node directories*."

## Invariants

- Missing package message files are treated as empty and created on first write.
- DagMessage writes to package files are atomic.
