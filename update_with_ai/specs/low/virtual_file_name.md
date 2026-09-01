<!-- Dependencies (md files to read alongside this one):
-->

# Interface LLS: virtual_file_name

## Data Types
```python
from typing import Protocol, TypeAlias, Sequence, Mapping, Optional

VirtualFileName: TypeAlias = str
WorkspaceFilePath: TypeAlias = str
VirtualFileMapping: TypeAlias = Mapping[VirtualFileName, WorkspaceFilePath]
UnsanitizedContent: TypeAlias = str
SanitizedContent: TypeAlias = str

class VirtualFileMapper(Protocol):
    def get_mappings(self) -> VirtualFileMapping: ...
    def to_virtual_name(self, host_path: WorkspaceFilePath) -> Optional[VirtualFileName]: ...
    def to_host_path(self, virtual_name: VirtualFileName) -> Optional[WorkspaceFilePath]: ...
    def sanitize_text(self, text: UnsanitizedContent) -> SanitizedContent: ...

class VirtualFileMapperFactory(Protocol):
    def create_mapper(self, workspace_files: Sequence[WorkspaceFilePath], workspace_root: Optional[str] = None) -> VirtualFileMapper: ...
```

- `VirtualFileName` → corresponds to *virtual file name*: a minimal unambiguous path used by an agent to refer to a workspace file.
- `WorkspaceFilePath` → corresponds to workspace file path.
- `VirtualFileMapping` → corresponds to *virtual file mapping*: bidirectional association between virtual file names and host file paths.
- `UnsanitizedContent` → corresponds to raw text containing host paths.
- `SanitizedContent` → corresponds to text with host paths replaced by virtual file names.
- `VirtualFileMapper` → corresponds to *virtual file mapper*: utility that translates paths, resolves collisions, and sanitizes text.
- `VirtualFileMapperFactory` → corresponds to *virtual file mapper factory*: provider constructing virtual file mappers for workspace paths.

## Term definitions

- **virtual file name** → the `VirtualFileName` alias
- **virtual file mapping** → the `VirtualFileMapping` alias
- **virtual file mapper** → term definition: a utility that translates between host paths and virtual file names and sanitizes text
- **virtual file mapper factory** → term definition: a provider constructing virtual file mappers for collections of workspace paths

## Component-Provided Operations

### `get_mappings`

```python
def get_mappings(self) -> VirtualFileMapping: ...
```

**Purpose:** (VirtualFileMapper) Retrieves the complete dictionary mapping virtual file names to underlying host file paths.

**Preconditions:** None.

**Postconditions:**
- Returns the full `VirtualFileMapping`.

**Failure Handling:** Always succeeds.

**HLS Justification:** "A *virtual file mapper* is a utility that derives *virtual file mappings* from workspace file paths."

### `to_virtual_name`

```python
def to_virtual_name(self, host_path: WorkspaceFilePath) -> Optional[VirtualFileName]: ...
```

**Purpose:** (VirtualFileMapper) Translates a full or workspace-relative host path to its corresponding virtual file name.

**Preconditions:** None.

**Postconditions:**
- Returns the matching `VirtualFileName`, or `None` if the host path is unmapped.

**Failure Handling:** Unmapped paths return `None`.

**HLS Justification:** "A *virtual file mapper* translates a *virtual file name* to its underlying host file path, and a host file path to its corresponding *virtual file name*."

### `to_host_path`

```python
def to_host_path(self, virtual_name: VirtualFileName) -> Optional[WorkspaceFilePath]: ...
```

**Purpose:** (VirtualFileMapper) Translates a virtual file name to its underlying host file path.

**Preconditions:** None.

**Postconditions:**
- Returns the matching `WorkspaceFilePath`, or `None` if the virtual file name is unmapped.

**Failure Handling:** Unmapped names return `None`.

**HLS Justification:** "A *virtual file mapper* translates a *virtual file name* to its underlying host file path, and a host file path to its corresponding *virtual file name*."

### `sanitize_text`

```python
def sanitize_text(self, text: UnsanitizedContent) -> SanitizedContent: ...
```

**Purpose:** (VirtualFileMapper) Replaces all occurrences of absolute host paths and workspace-relative paths in text with virtual file names in descending order of path length.

**Preconditions:** None.

**Postconditions:**
- Returns sanitized text with host paths substituted with virtual file names.

**Failure Handling:** Always succeeds.

**HLS Justification:** "Transforming text through a *virtual file mapper* replaces occurrences of full absolute paths and workspace-relative paths with *virtual file names* in descending path length order."

### `create_mapper`

```python
def create_mapper(self, workspace_files: Sequence[WorkspaceFilePath], workspace_root: Optional[str] = None) -> VirtualFileMapper: ...
```

**Purpose:** (VirtualFileMapperFactory) Constructs a virtual file mapper for a collection of workspace files.

**Preconditions:** None.

**Postconditions:**
- Returns a `VirtualFileMapper` deriving minimal disambiguated virtual file names.

**Failure Handling:** Always succeeds.

**HLS Justification:** "Creating a *virtual file mapper* through a *virtual file mapper factory* yields a *virtual file mapper* initialized with *virtual file mappings* for a collection of workspace file paths."

## Invariants

- Each `VirtualFileName` uniquely identifies at most one file in the mapping.
- Minimal bare filenames are used when distinct; collisions prepend shortest unique parent path segments.
- Path sanitization substitutes longer host paths before shorter substring paths.
