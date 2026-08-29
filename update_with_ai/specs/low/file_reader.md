<!-- Dependencies (md files to read alongside this one):
  - tool_provider.md
-->

# Interface LLS: file_reader

## Data Types
```python
from typing import Any, Protocol, TypeAlias
from dataclasses import dataclass
from tool_provider import ToolDefinition, PresentedToolResult, ToolCallOutcome

VirtualName: TypeAlias = str
FilePath: TypeAlias = str
FileMapping: TypeAlias = dict[VirtualName, FilePath]
ReadablePaths: TypeAlias = list[VirtualName]
SearchResultLimit: TypeAlias = int

@dataclass
class FileReaderConfig:
    file_mappings: FileMapping
    readable_paths: ReadablePaths
    search_result_limit: SearchResultLimit = 5
    session_start_reads_enabled: bool = True

class FileReader(Protocol):
    def get_tool_definitions(self) -> list[ToolDefinition]: ...
    def get_session_start_reads(self) -> list[PresentedToolResult]: ...
    def read_file(self, file_path: VirtualName, include_line_numbers: bool = False) -> ToolCallOutcome: ...
    def search_files(self, path: VirtualName = ".", pattern: str = "", offset: int | None = None, limit: int | None = None) -> ToolCallOutcome: ...
    def sanitize_paths(self, text: str) -> str: ...
    def resolve_path(self, file_path: VirtualName) -> str | None: ...
    def is_readable(self, file_path: VirtualName) -> bool: ...
```

## Term definitions

- **virtual name** → the `VirtualName` alias (definition in Data Types)
- **line-numbered view** → term definition: a view of a file's content where each line is prefixed with its 1-indexed line number
- **session-start read** → the `PresentedToolResult` type returned by `get_session_start_reads`
- **tool result** → the `ToolResult` type from tool_provider
- **tool failure** → the `ToolFailure` type from tool_provider
- **tool call** → the `ToolCall` alias from tool_provider
- **supersession flag** → term definition from tool_provider

## Component-Provided Operations

### `get_tool_definitions`

```python
def get_tool_definitions(self) -> list[ToolDefinition]
```

**Purpose:** Return the read and search tool definitions for the agent session.

**Preconditions:** None.

**Postconditions:**
- Returns definitions for `read_file` and `search_files` conforming to JSON schema.

**Failure Handling:** Always succeeds.

**HLS Justification:** "Request tool definitions (per tool_provider)."

### `get_session_start_reads`

```python
def get_session_start_reads(self) -> list[PresentedToolResult]
```

**Purpose:** Provide plain reads of readable non-writable files at run start before the agent's first turn.

**Preconditions:** None.

**Postconditions:**
- When session-start reads are enabled, returns a list of `PresentedToolResult` entries sorted by virtual name.
- When disabled, returns an empty list.
- Requesting reads changes no state.

**Failure Handling:** Missing files are skipped without failure.

**HLS Justification:** "Provide session-start reads for non-writable files."

### `read_file`

```python
def read_file(self, file_path: VirtualName, include_line_numbers: bool = False) -> ToolCallOutcome
```

**Purpose:** Read a file's entire content by virtual name.

**Preconditions:**
- `file_path` is a known virtual name.

**Postconditions:**
- On success: returns a single `ToolResult` with the file content.
- Reads of non-writable files never set supersedes.
- Reading an existing writable file requires `include_line_numbers=True`.

**Failure Handling:** Returns `ToolFailure` if unmapped, unreadable, or missing.

**HLS Justification:** "Read a file's content by virtual name."

### `search_files`

```python
def search_files(self, path: VirtualName = ".", pattern: str = "", offset: int | None = None, limit: int | None = None) -> ToolCallOutcome
```

**Purpose:** Search for a regex pattern across readable files.

**Preconditions:** None.

**Postconditions:**
- Returns matches rendered only for non-writable files; writable file matches are reported as counts in notes.
- Never sets supersedes.

**Failure Handling:** Returns `ToolFailure` on invalid regex or exceeded result limit.

**HLS Justification:** "Search for a regex pattern across readable files."

### `sanitize_paths`

```python
def sanitize_paths(self, text: str) -> str
```

**Purpose:** Replace real disk paths in strings with their virtual names.

**Preconditions:** None.

**Postconditions:**
- Replaces absolute filesystem paths with virtual names using longest-match first.

**Failure Handling:** Always succeeds.

**HLS Justification:** "Sanitize error messages and output by replacing real on-disk paths with virtual names."

## Invariants

- Reads of non-writable files never set supersedes.
- No state persists across sessions.

## Non-Concerns

- File writing and modification: handled by file_editor.
