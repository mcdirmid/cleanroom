<!-- Dependencies (md files to read alongside this one):
  - virtual_file_name.md
  - dag_storage.md
  - sandbox.md
  - build_graph_storage.md
  - build_message_store.md
-->

# Implementation LLS: build_graph_storage_impl

## Data Types
```python
from build_graph_storage import BuildGraphStorage
from build_message_store import BuildMessageStore

class BuildGraphStorageImpl(BuildGraphStorage):
    def __init__(self, message_store: BuildMessageStore) -> None: ...
```

## Behavioral Description

- Stores target node definitions, dependency graphs, and sandbox configurations in memory.
- Delegates pending message queueing, retrieval, clearing, and reverse dependency lookups to `BuildMessageStore`.
- Virtual file mappings assign distinct virtual file names for all declared readable and writable files of a node.
- Propagating dependencies exclude silent dependencies declared on a node, ensuring non-propagating dependencies do not mark dependents dirty.
- Provides thread-safe atomic queries for node dependencies and sandbox configurations.

## Invariants

- Configurations are immutable once loaded.
- Propagating dependencies exclude silent dependencies declared on a node.
