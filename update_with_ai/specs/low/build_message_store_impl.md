<!-- Dependencies (md files to read alongside this one):
  - dag_storage.md
  - node_id_utils.md
  - build_message_store.md
  - update_with_ai_proto_ext.md
-->

# Implementation LLS: build_message_store_impl

## Data Types
```python
from build_message_store import BuildMessageStore
from node_id_utils import NodeIdUtils, WorkspaceRootPath

class BuildMessageStoreImpl(BuildMessageStore):
    def __init__(self, workspace_root: WorkspaceRootPath, node_id_utils: NodeIdUtils) -> None: ...
```

## Behavioral Description

- Uses `node_id_utils.extract_node_directory` with `workspace_root` to locate package directories.
- Serializes node pending messages and reverse dependencies into `.update_with_ai.textproto` files using `ProtoPackageStore`.
- All nodes within a package directory share a single `.textproto` file.
- Reads and writes to package textproto files are atomic.

## Invariants

- Preserves existing messages on atomic update failures.
