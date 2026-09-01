<!-- Dependencies (md files to read alongside this one):
  - tool_provider.md
  - virtual_file_name.md
-->

# Interface LLS: file_reader

## Data Types
```python
from typing import Protocol, TypeAlias, Sequence, Optional
from dataclasses import dataclass
from tool_provider import Tool, ToolProvider, ToolResult, ToolFailure
from virtual_file_name import VirtualFileName, VirtualFileMapping, UnsanitizedContent, SanitizedContent

HostPath: TypeAlias = str
ReadOnlyFile: TypeAlias = VirtualFileName
ReadWriteFile: TypeAlias = VirtualFileName

@dataclass(frozen=True)
class FileReaderConfig:
    read_only_files: Sequence[ReadOnlyFile]
    read_write_files: Sequence[ReadWriteFile]
    file_mappings: VirtualFileMapping
    step_mode_guide: Optional[VirtualFileName] = None
    search_result_limit: Optional[int] = None

SessionStartRead: TypeAlias = ToolResult

class FileReader(ToolProvider, Protocol):
    def get_read_tool(self) -> Tool: ...
    def get_search_tool(self) -> Tool: ...
    def get_session_start_reads(self) -> Sequence[SessionStartRead]: ...
    def sanitize_paths(self, content: UnsanitizedContent) -> SanitizedContent: ...

class FileReaderFactory(Protocol):
    def create_file_reader(self, config: FileReaderConfig) -> FileReader: ...
```

- `HostPath` → corresponds to host filesystem path.
- `ReadOnlyFile` → corresponds to *read-only file*: a file accessible for reading in plain content form.
- `ReadWriteFile` → corresponds to *read-write file*: a file accessible for reading in line-numbered form and modification.
- `UnsanitizedContent` → corresponds to output content prior to path sanitization.
- `SanitizedContent` → corresponds to output content following path sanitization.
- `FileReaderConfig` → corresponds to *file reader configuration*: declared read-only files, read-write files, and host path mappings.
- `SessionStartRead` → corresponds to *session-start read*: a *tool result* generated from a *read-only file* before the first agent turn.
- `FileReader` → corresponds to *file reader*: a *tool provider* providing a *file read tool* and a *file search tool*.
- `FileReaderFactory` → corresponds to *file reader factory*: a provider that constructs *file readers* configured for specific sessions.

## Term definitions

- **read-only file** → the `ReadOnlyFile` alias
- **read-write file** → the `ReadWriteFile` alias
- **file reader configuration** → the `FileReaderConfig` alias
- **file read tool** → term definition: a *tool* (returned by `get_read_tool`) that reads content from a *read-only file* or *read-write file*
- **file search tool** → term definition: a *tool* (returned by `get_search_tool`) that searches file contents matching a pattern
- **file reader** → term definition: a *tool provider* providing a *file read tool* and a *file search tool*
- **file reader factory** → term definition: a provider that constructs *file readers* configured for specific sessions
- **session-start read** → the `SessionStartRead` alias

## Component-Provided Operations

### `get_read_tool`

```python
def get_read_tool(self) -> Tool: ...
```

**Purpose:** (FileReader) Retrieves the file reading tool instance.

**Preconditions:** None.

**Postconditions:**
- Returns a `Tool` executing reads on `VirtualFileName` targets: formatted with line numbers on `ReadWriteFile`, or plain content on `ReadOnlyFile`.

**Failure Handling:**
- Reading a step-mode guide produces a `ToolFailure` explaining that the guide is delivered progressively via advance execution.
- Unmapped or inaccessible virtual file names produce a `ToolFailure` listing all available readable virtual file names.

**HLS Justification:** "Executing a *file read tool* on a guide configured for progressive step delivery produces a *tool failure* explaining that the guide is delivered progressively via advance execution."

### `get_search_tool`

```python
def get_search_tool(self) -> Tool: ...
```

**Purpose:** (FileReader) Retrieves the file pattern search tool instance.

**Preconditions:** None.

**Postconditions:**
- Returns a `Tool` searching matching patterns across accessible workspace files.

**Failure Handling:** Invalid regex patterns produce a `ToolFailure`.

**HLS Justification:** "A *file reader* provides a *file read tool* and a *file search tool*."

### `get_session_start_reads`

```python
def get_session_start_reads(self) -> Sequence[SessionStartRead]: ...
```

**Purpose:** (FileReader) Generates plain content tool results for declared read-only files at session startup.

**Preconditions:** None.

**Postconditions:**
- Returns a sequence of `SessionStartRead` results for all configured `ReadOnlyFile` targets.

**Failure Handling:** Missing read-only files are skipped without halting session initialization.

**HLS Justification:** "A *file reader* produces *session-start reads* for declared *read-only files*."

### `sanitize_paths`

```python
def sanitize_paths(self, content: UnsanitizedContent) -> SanitizedContent: ...
```

**Purpose:** (FileReader) Replaces absolute host paths in output content with their corresponding virtual file names.

**Preconditions:** None.

**Postconditions:**
- Returns sanitized content with host paths substituted by `VirtualFileName` values in descending path length order.

**Failure Handling:** Always succeeds.

**HLS Justification:** "Transforming text through a *file reader* replaces host paths with *virtual file names*."

### `create_file_reader`

```python
def create_file_reader(self, config: FileReaderConfig) -> FileReader: ...
```

**Purpose:** (FileReaderFactory) Creates a file reader instance configured with permissions and path mappings.

**Preconditions:** None.

**Postconditions:**
- Returns a `FileReader` configured with `config`.

**Failure Handling:** Always succeeds.

**HLS Justification:** "Creating a *file reader* through a *file reader factory* yields a *file reader* configured from a *file reader configuration*."

## Invariants

- Executing the read tool on a `ReadWriteFile` formats lines with 1-indexed numbers.
- Executing the read tool on a `ReadOnlyFile` produces plain unnumbered content.
- Path sanitization substitutes host paths deterministically using virtual file mappings.
