<!-- Dependencies (md files to read alongside this one):
  - virtual_file_name.md
-->

# Implementation LLS: virtual_file_name_impl

## Data Types
```python
from typing import Optional, Sequence
from virtual_file_name import (
    VirtualFileName,
    WorkspaceFilePath,
    VirtualFileMapping,
    UnsanitizedContent,
    SanitizedContent,
    VirtualFileMapper,
    VirtualFileMapperFactory,
)

class _VirtualFileMapperImpl(VirtualFileMapper):
    def __init__(self, workspace_files: Sequence[WorkspaceFilePath], workspace_root: Optional[str] = None) -> None: ...

class VirtualFileMapperFactoryImpl(VirtualFileMapperFactory):
    def __init__(self) -> None: ...
```

## Behavioral Description

- `VirtualFileMapperFactoryImpl.create_mapper` constructs a `_VirtualFileMapperImpl` configured with workspace files and optional workspace root directory.
- `_VirtualFileMapperImpl` normalizes full absolute host paths by stripping the workspace root directory into workspace-relative paths.
- Computes minimal unique `VirtualFileName` values by using bare filenames when distinct across the collection, and prepending shortest unique parent path segments when collisions occur.
- `get_mappings` produces the derived mapping from `VirtualFileName` to `WorkspaceFilePath`.
- `to_virtual_name` resolves a full host path or workspace-relative path to its `VirtualFileName`, or returns `None` if unmapped.
- `to_host_path` resolves a `VirtualFileName` to its mapped `WorkspaceFilePath`, or returns `None` if unmapped.
- `sanitize_text` substitutes occurrences of host paths (both full absolute paths and workspace-relative paths) with `VirtualFileName` in descending order of path length.

## Invariants

- Every `VirtualFileName` uniquely maps to exactly one workspace file.
- Disambiguation resolves collisions by prepending minimal parent path segments.
- Path sanitization replaces longer host path strings before shorter substrings.
