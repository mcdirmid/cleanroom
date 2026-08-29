<!-- Dependencies (md files to read alongside this one):
  - dag_storage.md
  - build_graph_storage.md
  - build_message_store.md
  - manifest_node_loader.md
-->

# Implementation LLS: build_graph_storage_impl

## Data Types
```python
from build_graph_storage import BuildGraphStorage, GraphConfig
from build_message_store import BuildMessageStore
from manifest_node_loader import ManifestNodeLoader

class BaseBuildGraphStorageImpl(BuildGraphStorage):
    def __init__(self, config: GraphConfig, message_store: BuildMessageStore, manifest_loader: ManifestNodeLoader) -> None: ...

class BuildGraphStorageFileImpl(BaseBuildGraphStorageImpl):
    def __init__(self, config: GraphConfig, message_store: BuildMessageStore, manifest_loader: ManifestNodeLoader) -> None: ...
```

## Behavioral Description
Implements BuildGraphStorage by coordinating `BuildMessageStore` for message persistence and `ManifestNodeLoader` for manifest resolution.

## Invariants
- Graph resolution delegates to ManifestNodeLoader.
- Message file read/write operations delegate to BuildMessageStore.
