<!-- Dependencies (md files to read alongside this one):
  - dag_storage.md
  - node_id_utils.md
  - bazel_node_id_utils.md
  - bazel_target_labels_ext.md
-->

# Implementation LLS: bazel_node_id_utils_impl

## Data Types
```python
from bazel_node_id_utils import BazelNodeIdUtils

class BazelNodeIdUtilsImpl(BazelNodeIdUtils):
    def __init__(self) -> None: ...
```

## Behavioral Description

- Uses `bazel_target_labels_ext` functions to canonicalize raw target labels to `//pkg:target` format.
- Extracts the package part from canonical `NodeId` and joins with `workspace_root` to determine the directory.

## Invariants

- Strips repository qualifiers and normalizes labels starting with `//`.
