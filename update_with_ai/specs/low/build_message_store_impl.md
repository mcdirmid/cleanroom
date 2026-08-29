<!-- Dependencies (md files to read alongside this one):
  - build_message_store.md
  - dag_storage.md
  - build_graph_storage.md
-->

# Implementation LLS: build_message_store_impl

## Data Types
```python
from build_message_store import BuildMessageStore

class BuildMessageStoreImpl(BuildMessageStore):
    def __init__(self) -> None: ...
```

## Behavioral Description
Implements BuildMessageStore by parsing and serializing `.update_with_ai.textproto` protobuf text-format files.

## Invariants
- Escaped strings in textproto match standard protobuf literal syntax.
