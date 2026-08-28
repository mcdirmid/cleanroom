<!-- Dependencies (md files to read alongside this one):
  - tool_provider.md
-->

# Interface LLS: file_view

## Data Types
```python
from dataclasses import dataclass
from typing import Protocol, TypeAlias
from tool_provider import (
    PresentedToolResult,
    ToolCallOutcome,
    ToolDefinition,
)

VirtualName: TypeAlias = str

FilePath: TypeAlias = str

FileMapping: TypeAlias = dict[VirtualName, FilePath]

ReadablePaths: TypeAlias = list[VirtualName]

WritablePaths: TypeAlias = list[VirtualName]

TemplateMapping: TypeAlias = dict[VirtualName, str]

SearchResultLimit: TypeAlias = int

WriteOccurred: TypeAlias = bool

@dataclass
class FileViewConfig:
    file_mappings: FileMapping
    readable_paths: ReadablePaths
    writable_paths: WritablePaths
    templates: TemplateMapping
    search_result_limit: SearchResultLimit
    session_start_reads_enabled: bool

class FileView(Protocol):
    def get_tool_definitions(self) -> list[ToolDefinition]: ...
    def get_session_start_reads(self) -> list[PresentedToolResult]: ...
    def read_file(self, file_path: VirtualName, include_line_numbers: bool = False) -> ToolCallOutcome: ...
    def edit_file(self, file_path: VirtualName, old_str: str, new_str: str, expect_multiple: bool = False) -> ToolCallOutcome: ...
    def replace_lines(self, file_path: VirtualName, start_line: int, end_line: int, new_str: str) -> ToolCallOutcome: ...
    def search_files(self, path: VirtualName, pattern: str, offset: int | None = None, limit: int | None = None) -> ToolCallOutcome: ...
    def get_write_occurred(self) -> WriteOccurred: ...
```

`FileViewConfig` is the client-supplied configuration for the file machinery: file mappings (each file's virtual name to its full path), the readable and writable virtual names, the templates (a mapping from writable virtual names to their template content), the search result limit (the maximum rendered matches a single search may return), and whether session-start reads are enabled.
## Term definitions

- **virtual name** → the `VirtualName` alias (definition in Data Types): the name the agent uses to address a file — the file's final path component when no other configured file shares it, otherwise the shortest path suffix unique among the configured files; file_view resolves the virtual name to the file's full filesystem path via `file_mappings`, and reads, writes, edits, searches, session-start reads, and error messages name files by virtual name, never by path
- **file write** → term definition: any successful operation that modifies the filesystem; a file write sets the write-occurred flag
- **line-numbered view** → term definition: a rendering of a file's content with each line prefixed by its 1-indexed line number (`"N │ line"`); the line numbers are metadata, never file content
- **injected read** → term definition: the read provided for a file immediately after a successful file write of that file, presenting a read request with line numbers and the read result carrying the file's full current content; the agent did not request it, and to the agent it appears as a numbered read it requested; a write that fails provides no injected read
- **session-start read** → term definition: a read of a file the agent can read but not write, provided at run start for rendering before the agent's first turn; it renders the file's content plain, never supersedes an earlier result, and is never stubbed
- **template** → term definition: a writable file's initial content, configured for the file (realized as the `TemplateMapping` type); when the file does not exist when file_view is configured, the file is created with the template's content at run start, and a file that exists when file_view is configured is never modified by its template; template initialization is not a file write — it never signals that the filesystem was modified and is never a changed file
- **stubbing** → term definition: these rules apply to all file_view operations that produce a `ToolResult`; stubbing follows `tool_provider` semantics — when a result's `supersedes` flag is set, the earlier non-stubbed result for the same file is replaced by a placeholder, keeping the conversation focused on current state; a result with the flag unset supersedes nothing, and at most one earlier result is superseded per result
- **tool definition** → the `ToolDefinition` alias from tool_provider
- **tool result** → the `ToolResult` type from tool_provider
- **supersession flag** → term definition from tool_provider
- **stub** → term definition from tool_provider
- **tool failure** → the `ToolFailure` type from tool_provider

## Component-Provided Operations

### `get_tool_definitions`

```python
def get_tool_definitions(self) -> list[ToolDefinition]
```

**Purpose:** Return the file tools' definitions: reading the entire file, writing, content-based editing, line-range editing, and searching.

**Preconditions:** file_view has been configured with file mappings and readable/writable paths.

**Postconditions:** Returns a list containing exactly the `read_file`, `edit_file`, `replace_lines`, and `search_files` tool definitions. Each definition follows the JSON schema format expected by the model (as defined in `tool_provider`).

**Failure Handling:** No failure conditions.

**HLS Justification:** "Request tool definitions (per tool_provider)."


### `get_session_start_reads`

```python
def get_session_start_reads(self) -> list[PresentedToolResult]
```

**Purpose:** Return the session-start reads: the plain reads of the read-only files, for rendering at the beginning of a run before the model's first turn.

**Preconditions:** None.

**Postconditions:**
- When `session_start_reads_enabled` is set: returns a session-start read (per the session-start read rules) for every file in `readable_paths` that is not in `writable_paths`, sorted by virtual name
- When `session_start_reads_enabled` is unset: returns an empty list
- Each session-start read is a `PresentedToolResult` pairing the `read_file` call with its plain read result; each result's `supersedes` is unset
- Requesting the session-start reads changes no file_view state

**Failure Handling:** Always succeeds; filesystem errors reading a readable file are unhandled.

**HLS Justification:** "Request the session-start reads."


### `read_file`

```python
def read_file(self, file_path: VirtualName, include_line_numbers: bool = False) -> ToolCallOutcome
```

**Purpose:** Read a file's entire content using the virtual name provided by the agent.

**Preconditions:**
- `file_path` must exist in `file_mappings` and be in `readable_paths`
- `include_line_numbers` may be `True` only when `file_path` is in `writable_paths` (line numbers serve `replace_lines` edits)
- `include_line_numbers` must be `True` when `file_path` is in `writable_paths` and the file already exists on disk (a plain read of an existing writable file is rejected; line numbers are metadata, not file content)

**Postconditions:**
- Returns the file's entire content as a string in `content`; reads are not paginated and are not bounded by a size limit
- When `include_line_numbers` is `True`: each line is prefixed with its 1-indexed line number (`"N │ line"`); the file's view for the run becomes line-numbered
- When `include_line_numbers` is `False` (a non-writable file): lines are returned without prefixes
- `supersedes` is `True` when `file_path` is in `writable_paths` (the result supersedes the earlier result for that file, per the stubbing rules) and `False` when `file_path` is not in `writable_paths`
- `content` is the file's content in the file's current view
- The result's `note` reports the file's line count and view

**Failure Handling:**
- Policy violation (file_path not in readable_paths or file_mappings) → Return `ToolFailure[T_tool]` with the error message identifying the violated policy.
- Invalid parameters (`include_line_numbers` requested for a non-writable file) → Return `ToolFailure[T_tool]` with the error message describing the parameter error.
- Writable file already exists and `include_line_numbers` is `False` → Return `ToolFailure[T_tool]` advising the agent to call `read_file` with `include_line_numbers=True` (line numbers are metadata, never file content).
- Filesystem errors are unhandled (no contract specified in this interface spec).

**HLS Justification:** A read provides the file's entire content; a writable-file read supersedes the file's earlier result, keeping the conversation current.


### `edit_file`

```python
def edit_file(self, file_path: VirtualName, old_str: str, new_str: str,
              expect_multiple: bool = False) -> ToolCallOutcome
```

**Purpose:** Replace text in a file by content-based search and replace.

**Preconditions:**
- `file_path` must exist in `file_mappings` and be in `writable_paths`
- `old_str` must be non-empty and at most 100 characters; `new_str` must be at most 100 characters (edit_file is for short search/replace pairs; whole-file and large edits go through `replace_lines`)
- The file must exist on disk (edits modify existing files only)

**Postconditions:**
- When `expect_multiple` is `False`: exactly one occurrence of `old_str` is replaced with `new_str`; when `True`: every occurrence is replaced
- The file is written with the replacement applied; the write-occurred flag is set (per the file write rules)
- The outcome is a sequence of two results, per the injected read rules: a write confirmation (a `ToolResult` with `supersedes` set to `True`; it supersedes the earlier result for that file) and an injected read
- The write confirmation's `content` and `note` are minimal: a structured success message (with counts where relevant); no file content is echoed in it
- An edit's replacement applies atomically (all or nothing)

**Failure Handling:**
- Policy violation (file_path not in writable_paths or file_mappings) → Return `ToolFailure[T_tool]` with the error message identifying the violated policy.
- Invalid arguments (empty `old_str`; `old_str` identical to `new_str` — the edit would change nothing; `old_str` or `new_str` exceeding 100 characters) → Return `ToolFailure[T_tool]` with the error message describing the argument error; an over-length string error advises `replace_lines` (which requires the line-numbered view).
- `old_str` absent from the file → Return `ToolFailure[T_tool]` stating it was not found.
- More than one match with `expect_multiple` `False` → Return `ToolFailure[T_tool]` stating the match count and advising `expect_multiple=True` or a narrower `old_str`.
- Filesystem errors are unhandled (no contract specified in this interface spec).

**HLS Justification:** Content-based editing: search-and-replace of short text, bounded in length; longer changes go through line-range editing.


### `replace_lines`

```python
def replace_lines(self, file_path: VirtualName, start_line: int, end_line: int,
                  new_str: str) -> ToolCallOutcome
```

**Purpose:** Replace, delete, or insert lines in a file by 1-indexed line range. The tool definition for this operation marks all four parameters (`file_path`, `start_line`, `end_line`, `new_str`) as required in its JSON schema (`required` list).

**Preconditions:**
- `file_path` must exist in `file_mappings` and be in `writable_paths`
- `start_line` must be between 1 and `len(file) + 1`; `end_line` must be between 0 and `len(file)`
- `start_line` and `end_line` must be integers
- The file must exist on disk (edits modify existing files only)
- The file's current view must be line-numbered (a write resets the view to plain; the injected read after a write re-enables the line-numbered view, so a `replace_lines` may follow a write without a further read)

**Postconditions:**
- Lines `start_line` through `end_line` (inclusive) are replaced with `new_str`; `start_line > end_line` inserts `new_str` before line `start_line` (no lines removed); empty `new_str` deletes the range; a trailing newline is preserved when the file had one and lines remain
- The file is written with the change applied; the write-occurred flag is set (per the file write rules)
- The outcome is a sequence of two results, per the injected read rules: a write confirmation (a `ToolResult` with `supersedes` set to `True`; it supersedes the earlier result for that file) and an injected read
- The write confirmation's `content` and `note` are minimal: a structured success message (with counts where relevant); no file content is echoed in it
- The replacement applies atomically (all or nothing)

**Failure Handling:**
- Policy violation (file_path not in writable_paths or file_mappings) → Return `ToolFailure[T_tool]` with the error message identifying the violated policy.
- The file's current view is not line-numbered → Return `ToolFailure[T_tool]` advising `read_file(file_path, include_line_numbers=True)` before editing and noting that a write invalidated the line numbers when the view became plain due to a write; the failure supersedes nothing and removes nothing.
- Invalid arguments (non-integer line numbers, or `start_line`/`end_line` out of bounds) → Return `ToolFailure[T_tool]` with the error message describing the argument error and the file's line count.
- Filesystem errors are unhandled (no contract specified in this interface spec).

**HLS Justification:** Line-range editing: replace, delete, insert; a line-range edit requires the line-numbered view.


### `search_files`

```python
def search_files(self, path: VirtualName, pattern: str,
                 offset: int | None = None,
                 limit: int | None = None) -> ToolCallOutcome
```

**Purpose:** Search for a pattern in files using the virtual path provided by the agent.

**Preconditions:**
- `path` must be in `readable_paths`
- `pattern` must be a valid regex pattern
- If `offset` provided, must be non-negative
- If `limit` provided, must be positive and must not exceed the search result limit

**Postconditions:**
- Returns up to `limit` rendered matches (or all rendered matches when `limit` is omitted and the total fits within the search result limit) as string in `content`, paged from `offset`
- Rendered matches are matches found in files that are not writable; matches found in writable files are never rendered
- Searches recursively within the specified path
- `supersedes` is `False` (search results never supersede an earlier result)
- The result's `note` reports the total rendered matches, how many remain after this page, the offset to continue from, and the count of suppressed matches in writable files

**Failure Handling:**
- Policy violation (path not in readable_paths) → Return `ToolFailure[T_tool]` with the error message identifying the violated policy.
- Invalid pattern (not a valid regex) → Return `ToolFailure[T_tool]` with the error message describing the pattern error.
- Invalid parameters (negative offset, zero limit, limit above the search result limit, or an omitted limit whose rendered matches exceed the search result limit) → Return `ToolFailure[T_tool]` with the error message describing the parameter error and advising offset/limit pagination.
- Filesystem errors are unhandled (no contract specified in this interface spec).

**HLS Justification:** Recursive searching within a specified path; search results beyond the search result limit signal a tool failure advising offset/limit pagination.


### `get_write_occurred`

```python
def get_write_occurred(self) -> WriteOccurred
```

**Purpose:** Return whether the agent has modified the filesystem during the current run.

**Preconditions:** None.

**Postconditions:** Returns `True` if any file write has succeeded during the current run; `False` otherwise.

**Failure Handling:** Always succeeds.

**HLS Justification:** "Query whether any file write has occurred."

## Invariants

- No state persists across runs
- Every `templates` entry names a writable file (a virtual name in `writable_paths`)
- The write-occurred flag is monotonic (once `True`, never `False`)
- All policy checks occur before any filesystem mutation
- Errors leave the filesystem unchanged
- A result with `supersedes` set supersedes the earlier non-stubbed result for the same file; a result with `supersedes` unset supersedes nothing
- A result supersedes at most one earlier result (at most one non-stubbed result exists per file at any time)
- A write or edit supersedes the file's earlier read result; the injected read provides the file's current content in the conversation
- An edit's replacement applies atomically (all or nothing): a replacement is never partially applied
- `replace_lines` requires the line-numbered view
- Search results never render matches from writable files
- A tool result never carries the stub text

## Non-Concerns

- **Error message wording:** error messages identify the violated policy or the failing operation; their exact wording is unspecified.
- **Session-start read size:** session-start reads inherit the unbounded-read rule; the read-only files are assumed to be reasonably sized, so no separate size bound is introduced for session-start reads.
- **Template size:** templates are assumed to be reasonably sized, so no separate size bound is introduced for template content.
- **Virtual-name derivation:** the exact procedure that selects the shortest unique suffix is unspecified; the resulting virtual names follow the virtual name definition.
- **Multiple-occurrence edits:** the HLS's "search-and-replace of short text" does not pin whether an edit applies to one or all occurrences; the `expect_multiple` parameter pins it here (an edit without it applies to the first occurrence).
- **View handling:** the exact mechanism for tracking per-file view modes is unspecified.
