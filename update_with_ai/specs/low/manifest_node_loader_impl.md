<!-- Dependencies (md files to read alongside this one):
  - manifest_node_loader.md
  - build_graph_storage.md
  - sandbox.md
  - run_control.md
  - file_reader.md
  - file_editor.md
  - guide_delivery.md
  - dag_storage.md
-->

# Implementation LLS: manifest_node_loader_impl

## Data Types
```python
from manifest_node_loader import ManifestNodeLoader

class ManifestNodeLoaderImpl(ManifestNodeLoader):
    def __init__(self) -> None: ...
```

## Behavioral Description
Implements ManifestNodeLoader by discovering and reading target `.manifest.json` files from the filesystem and building `SandboxConfig` instances.

## Invariants
- Deterministic virtual file path assignment for sandbox file mappings.
