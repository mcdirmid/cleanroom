<!-- Dependencies (md files to read alongside this one):
  - file_reader.md
  - tool_provider.md
-->

# Interface LLS: file_editor

## Data Types
```python
from typing import Any, Protocol, TypeAlias
from dataclasses import dataclass
from file_reader import VirtualName
from tool_provider import ToolDefinition, ToolCallOutcome

WritablePaths: TypeAlias = list[VirtualName]
TemplateMapping: TypeAlias = dict[VirtualName, str]
WriteOccurred: TypeAlias = bool

@dataclass
class FileEditorConfig:
    writable_paths: WritablePaths
    templates: TemplateMapping | None = None

class FileEditor(Protocol):
    def get_tool_definitions(self) -> list[ToolDefinition]: ...
    def replace(self, file_path: VirtualName, old_str: str, new_str: str, expect_multiple: bool = False) -> ToolCallOutcome: ...
    def update_lines(self, file_path: VirtualName, start_line: int, end_line: int, new_str: str) -> ToolCallOutcome: ...
    def get_write_occurred(self) -> WriteOccurred: ...
    def get_changed_files(self) -> list[VirtualName]: ...
    def get_run_start_snapshot(self, file_path: VirtualName) -> str | None: ...
    def get_current_content(self, file_path: VirtualName) -> str | None: ...
    def is_writable(self, file_path: VirtualName) -> bool: ...
```

## Term definitions

- **virtual name** → the `VirtualName` alias from file_reader
- **line-numbered view** → term definition from file_reader
- **file write** → term definition: a mutation operation (replace or update_lines) that alters a writable file on disk
- **injected read** → term definition: an automatic re-read of a file with line numbers injected into the conversation following a successful write
- **template** → the `TemplateMapping` alias (definition in Data Types)
- **tool result** → the `ToolResult` type from tool_provider
- **supersession flag** → term definition from tool_provider
- **tool failure** → the `ToolFailure` type from tool_provider
- **tool call** → the `ToolCall` alias from tool_provider

## Component-Provided Operations

### `get_tool_definitions`

```python
def get_tool_definitions(self) -> list[ToolDefinition]
```

**Purpose:** Return the edit tool definitions (`replace`, `update_lines`).

**Preconditions:** None.

**Postconditions:**
- Returns JSON schema definitions for `replace` and `update_lines`.

**Failure Handling:** Always succeeds.

**HLS Justification:** "Request tool definitions (per tool_provider)."

### `replace`

```python
def replace(self, file_path: VirtualName, old_str: str, new_str: str, expect_multiple: bool = False) -> ToolCallOutcome
```

**Purpose:** Replace short text in a file (content-based replacement up to 200 characters).

**Preconditions:**
- `file_path` is a writable file.
- `old_str` and `new_str` do not exceed 200 characters.

**Postconditions:**
- On success: returns write confirmation and injected line-numbered read (both with `supersedes=True`), sets `write_occurred`, records changed file.

**Failure Handling:** Returns `ToolFailure` on length limit violation, missing old string, multiple matches without `expect_multiple`, or permissions.

**HLS Justification:** "Replace short text in a file (content-based replacement up to 200 characters)."

### `update_lines`

```python
def update_lines(self, file_path: VirtualName, start_line: int, end_line: int, new_str: str) -> ToolCallOutcome
```

**Purpose:** Replace, delete, or insert lines by 1-indexed line range.

**Preconditions:**
- `file_path` is a writable file and currently in line-numbered view.
- `start_line` and `end_line` are valid 1-indexed line numbers.

**Postconditions:**
- On success: returns write confirmation and injected line-numbered read (both with `supersedes=True`), sets `write_occurred`, records changed file.

**Failure Handling:** Returns `ToolFailure` if not writable, not in line-numbered view, or invalid line range.

**HLS Justification:** "Update lines in a file by 1-indexed line range (replacement, deletion, or insertion)."

### `get_write_occurred`

```python
def get_write_occurred(self) -> WriteOccurred
```

**Purpose:** Return whether any file write succeeded during the session.

**Preconditions:** None.

**Postconditions:**
- Returns True if any write succeeded; False otherwise.

**Failure Handling:** Always succeeds.

**HLS Justification:** "Query whether any file write occurred during the session."

### `get_changed_files`

```python
def get_changed_files(self) -> list[VirtualName]
```

**Purpose:** Return the list of changed files in write order (deduped).

**Preconditions:** None.

**Postconditions:**
- Returns virtual names of changed files.

**Failure Handling:** Always succeeds.

**HLS Justification:** "Query changed files, current content, and baseline run-start snapshots."

## Invariants

- Writes set the write_occurred flag and produce write confirmation plus injected read.
- Updating lines requires an active line-numbered view.
- Templates initialize missing files without setting write_occurred.

## Non-Concerns

- Diff generation: handled by run_control using baseline snapshots from file_editor.
