<!-- Dependencies (md files to read alongside this one):
  - tool_provider-low.md
  - dag_storage-low.md
  - dag_clean_logic-low.md
  - agent_loop-low.md
-->

# Interface LLS: sandbox

## Data Types

```python
from typing import Any, Callable, Protocol, TypeVar, Generic
from dataclasses import dataclass
from tool_provider import ToolDefinition, ToolResult, Signal, TerminateAgentWithSuccess, TerminateAgentWithFailure, TerminateSuccessResult, ToolFailure, ToolCallOutcome, T_tool
```

```python
VirtualName = str
```

```python
FilePath = str
```

```python
FileMapping = dict[VirtualName, FilePath]
```

```python
ReadablePaths = list[VirtualName]
```

```python
WritablePaths = list[VirtualName]
```

```python
BlameTargets = list[str]
```

```python
BlameTarget = str
```

```python
Feedback = str
```

```python
Blame = tuple[BlameTarget, Feedback]
```

`BlameTarget` identifies a node the agent may blame (a dependency of the current run). `Feedback` is the correction feedback on how to correct the blamed node's output. Each `Blame` pair corresponds to one feedback message to its target.

```python
ReadSizeLimit = int
```

```python
SearchResultLimit = int
```

```python
DiffSizeLimit = int
```

```python
VerificationCallback = Callable[[], tuple[bool, str]] | None
```

```python
@dataclass
class SandboxConfig:
    file_mappings: FileMapping
    readable_paths: ReadablePaths
    writable_paths: WritablePaths
    blame_targets: BlameTargets
    read_size_limit: ReadSizeLimit
    search_result_limit: SearchResultLimit
    diff_size_limit: DiffSizeLimit | None = None
    verification_callback: VerificationCallback = None
```

The client-supplied configuration for a sandbox: file mappings, readable and writable paths, blame targets, read size, search result, and diff size limits, and an optional verification callback.

```python
WriteOccurred = bool
```

```python
class Sandbox(Protocol):
    def get_tool_definitions(self) -> list[ToolDefinition]: ...
    def read_file(self, file_path: VirtualName, start_line: int = 1, end_line: int | None = None, include_line_numbers: bool = False) -> ToolCallOutcome: ...
    def write_file(self, file_path: VirtualName, content: str) -> ToolCallOutcome: ...
    def edit_file(self, file_path: VirtualName, old_str: str, new_str: str, expect_multiple: bool = False) -> ToolCallOutcome: ...
    def replace_lines(self, file_path: VirtualName, start_line: int, end_line: int, new_content: str) -> ToolCallOutcome: ...
    def search_files(self, path: VirtualName, pattern: str, offset: int | None = None, limit: int | None = None) -> ToolCallOutcome: ...
    def read_chunks(self, file_path: VirtualName, chunk_indices: list[int] | None = None, include_adjacent: bool = False) -> ToolCallOutcome: ...
    def replace_chunks(self, file_path: VirtualName, replacements: list[dict], encoding: str | None = None) -> ToolCallOutcome: ...
    def verify(self) -> ToolCallOutcome: ...
    def succeed(self, changes: list[dict[str, str]] = []) -> ToolCallOutcome: ...
    def fail(self) -> ToolCallOutcome: ...
    def blame(self, blames: list[Blame]) -> ToolCallOutcome: ...
    def get_write_occurred(self) -> WriteOccurred: ...
```

## Stubbing Semantics (term definition)

These rules apply to all sandbox operations that produce a `ToolResult` (i.e., when the `ToolCallOutcome` is a `ToolResult`).

- Read-file region overlap (read_file): A read region is the line range actually read: from `start_line` through the last line returned (a read truncated at end-of-file records the region ending at the last line of the file, not the requested end). Two regions overlap if they share any line. A read always returns the requested content; overlap never stubs the read itself. `stub_previous` is `True` if the current region overlaps with any previous non-stubbed region for the same file, stubbing the previous instances of the file's content in the conversation. A line-numbered read (`include_line_numbers=True`) sets `stub_previous` only for overlap with previous line-numbered reads, never with plain reads: the numbered view is distinct (it carries line numbers) and must remain obtainable so line-range edits can be grounded.
- Chunk overlap (read_chunks): a chunk read always returns the requested chunk content; `stub_previous` is `True` if the chunk indices whose content is returned (the requested indices plus any adjacent context included via `include_adjacent`) overlap with any previous non-stubbed chunk reads for the same file, stubbing the previous instances.
- Search dedup (search_files): `stub_previous` is `True` if the same `path`, `pattern`, `offset`, and `limit` were previously searched (paging through results with a new offset is a distinct search); the search itself always provides its results.
- A tool result never carries the stub text: stubbing (`stub_previous`) replaces previous tool results in the conversation; a tool call either succeeds with content or fails with an informative tool failure — never a stub.
- Unconditional stubbing: `write_file`, `edit_file`, `replace_lines`, `replace_chunks`, and `verify` always set `stub_previous=True`. Termination tools (`succeed`, `fail`, `blame`) never stub (`content_id` is `None`).
- Stub replacement text: stubbed content is replaced with a placeholder that clearly indicates removal (the exact placeholder text is pinned in the implementation spec). Stubbed messages retain their original position in the conversation.
- Notes: every successful read carries a `note` reporting how much content remains and how to continue (`start_line` for files, unread chunk indices for chunks, `offset` for searches). Reads and searches never provide the stub text; overlap only stubs the previous instances.
- Write-side effects on stubbing state: `write_file`, `edit_file`, `replace_lines`, and `replace_chunks` clear the per-file stubbing state (read regions, chunk indices, search dedup records) after a successful write.

## Component-Provided Operations

### `get_tool_definitions`

```python
def get_tool_definitions(self) -> list[ToolDefinition]
```

**Purpose:** Return the list of tool definitions available in the current sandbox configuration. Tools are conditionally included based on the configuration provided at initialization.

**Preconditions:** The sandbox has been configured with file mappings, readable/writable paths, and optional verification callback.

**Postconditions:** Returns a list of tool definitions. Each definition follows the JSON schema format expected by the model (as defined in `tool_provider`). The following tools are included:
- `read_file`, `write_file`, `edit_file`, `replace_lines`, `search_files`, `verify` (always)
- `read_chunks`, `replace_chunks` only if Python files are accessible
- `succeed`, `fail` (always)
- `blame` only if blame targets are non-empty

**Failure Handling:** No failure conditions.

**HLS Justification:** "The sandbox provides tool definitions that the agent loop can pass to the model."


### `read_file`

```python
def read_file(self, file_path: VirtualName, start_line: int = 1, end_line: int | None = None,
              include_line_numbers: bool = False) -> ToolCallOutcome
```

**Purpose:** Read lines from a file using the virtual name provided by the agent.

**Preconditions:**
- `file_path` must exist in `file_mappings` and be in `readable_paths`
- `start_line` must be a positive integer (1-indexed)
- If `end_line` provided, it must be an integer >= `start_line`
- `include_line_numbers` may be `True` only when `file_path` is in `writable_paths` (line numbers serve `replace_lines` edits)

**Postconditions:**
- Returns lines `start_line` through `end_line` (or the end of the file when `end_line` is omitted) as string in `content`
- When `include_line_numbers` is `True`, each line is prefixed with its 1-indexed line number (`"N \u2502 line"`); when `False`, lines are returned without prefixes
- A line-numbered read records its range as visible for line-range edits; any write clears all visible ranges for the file. Line-number mode is sticky: once a file is read with `include_line_numbers=True`, a plain read of it is a tool failure, ever.
- The read succeeds only when the returned content fits within the read size limit; otherwise the call fails
- `content_id` is the virtual file path
- `stub_previous` per stubbing semantics (read-file line-range overlap)
- The result's `note` reports how many lines were read, the file's line count, how many remain, and the next `start_line`; a stubbed read's note reports which region was already read and the next `start_line`

**Failure Handling:**
- Policy violation (file_path not in readable_paths or file_mappings) → Return `ToolFailure[T_tool]` with the error message identifying the violated policy.
- Invalid parameters (non-positive `start_line`, `end_line` below `start_line`, `include_line_numbers` requested for a non-writable file, or a read whose content would exceed the read size limit) → Return `ToolFailure[T_tool]` with the error message describing the parameter error and advising a smaller line range.
- Plain read after a line-numbered read of the same file (sticky line-number mode) → Return `ToolFailure[T_tool]` stating that the file was read with `include_line_numbers=true` and that plain reads of it are not allowed, ever — this is a tool failure, never a stub.
- Filesystem errors are unhandled (no contract specified in this interface spec).

**HLS Justification:** read_file signals stubbing on read line-range overlap for the same file.


### `write_file`

```python
def write_file(self, file_path: VirtualName, content: str) -> ToolCallOutcome
```

**Purpose:** Create a new file with content, using the virtual name provided by the agent.

**Preconditions:**
- `file_path` must exist in `file_mappings` and be in `writable_paths`
- Content must be non-empty
- The file must not already exist on disk (write_file creates new files only; modifying an existing file must go through `edit_file` or `replace_lines`)

**Postconditions:**
- File is created at the resolved path
- `write_occurred` flag set to `True`
- `content_id` is the virtual file path
- `stub_previous` is `True` (unconditional stubbing per stubbing semantics)
- Per-file stubbing state (read regions, chunk indices, search dedup records) for this file is cleared, so subsequent reads of the file will not be stubbed based on pre-write reads.
- The result is minimal: a structured success message (with counts where relevant); no file content is echoed

**Failure Handling:**
- Policy violation (file_path not in writable_paths or file_mappings) → Return `ToolFailure[T_tool]` with the error message identifying the violated policy.
- Invalid arguments (non-empty content required) → Return `ToolFailure[T_tool]` with the error message describing the argument error.
- File already exists → Return `ToolFailure[T_tool]` stating that write_file is only for creating new files and advising `edit_file` (content-based) or `replace_lines` (line-based).
- Filesystem errors are unhandled (no contract specified in this interface spec).

**HLS Justification:** write_file signals stubbing unconditionally for the file.


### `edit_file`

```python
def edit_file(self, file_path: VirtualName, old_str: str, new_str: str,
              expect_multiple: bool = False) -> ToolCallOutcome
```

**Purpose:** Replace text in a file by content-based search and replace.

**Preconditions:**
- `file_path` must exist in `file_mappings` and be in `writable_paths`
- `old_str` must be non-empty
- The file must exist on disk (edits modify existing files; use `write_file` to create new ones)

**Postconditions:**
- When `expect_multiple` is `False`: exactly one occurrence of `old_str` is replaced with `new_str`; when `True`: every occurrence is replaced
- The file is written with the replacement applied; `write_occurred` flag set to `True`
- `content_id` is the virtual file path
- `stub_previous` is `True` (unconditional stubbing per stubbing semantics)
- Per-file stubbing state (read regions, chunk indices, search dedup records) for this file is cleared, so subsequent reads of the file will not be stubbed based on pre-write reads.
- The result is minimal: a structured success message (with counts where relevant); no file content is echoed

**Failure Handling:**
- Policy violation (file_path not in writable_paths or file_mappings) → Return `ToolFailure[T_tool]` with the error message identifying the violated policy.
- Invalid arguments (empty `old_str`; `old_str` identical to `new_str` — the edit would change nothing) → Return `ToolFailure[T_tool]` with the error message describing the argument error.
- `old_str` absent from the file → Return `ToolFailure[T_tool]` stating it was not found.
- More than one match with `expect_multiple` `False` → Return `ToolFailure[T_tool]` stating the match count and advising `expect_multiple=True` or a narrower `old_str`.
- Filesystem errors are unhandled (no contract specified in this interface spec).

**HLS Justification:** edit_file is a file write: it signals stubbing unconditionally for the file and modifies the filesystem.


### `replace_lines`

```python
def replace_lines(self, file_path: VirtualName, start_line: int, end_line: int,
                  new_content: str) -> ToolCallOutcome
```

**Purpose:** Replace, delete, or insert lines in a file by 1-indexed line range.

**Preconditions:**
- `file_path` must exist in `file_mappings` and be in `writable_paths`
- `start_line` must be between 1 and `len(file) + 1`; `end_line` must be between 0 and `len(file)`
- `start_line` and `end_line` must be integers
- The file must exist on disk (edits modify existing files; use `write_file` to create new ones)
- The edited line range must be currently visible in context: covered by `read_file` calls with `include_line_numbers=True` since the file's last write (any write clears what is visible)

**Postconditions:**
- Lines `start_line` through `end_line` (inclusive) are replaced with `new_content`; `start_line > end_line` inserts `new_content` before line `start_line` (no lines removed); empty `new_content` deletes the range; a trailing newline is preserved when the file had one and lines remain
- The file is written with the change applied; `write_occurred` flag set to `True`
- `content_id` is the virtual file path
- `stub_previous` is `True` (unconditional stubbing per stubbing semantics)
- Per-file stubbing state (read regions, chunk indices, search dedup records) for this file is cleared, so subsequent reads of the file will not be stubbed based on pre-write reads.
- The result is minimal: a structured success message (with counts where relevant); no file content is echoed

**Failure Handling:**
- Policy violation (file_path not in writable_paths or file_mappings) → Return `ToolFailure[T_tool]` with the error message identifying the violated policy.
- Range not visible in context → Return `ToolFailure[T_tool]` advising `read_file(file_path, include_line_numbers=True, start_line=..., end_line=...)` of the range before editing.
- Invalid arguments (non-integer line numbers, or `start_line`/`end_line` out of bounds) → Return `ToolFailure[T_tool]` with the error message describing the argument error and the file's line count.
- Filesystem errors are unhandled (no contract specified in this interface spec).

**HLS Justification:** replace_lines is a file write: it signals stubbing unconditionally for the file and modifies the filesystem.


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
- Returns up to `limit` matches (or all matches when `limit` is omitted and the total fits within the search result limit) as string in `content`, paged from `offset`
- Searches recursively within the specified path
- `content_id` is the virtual path
- `stub_previous` per stubbing semantics (search dedup per path, pattern, offset, and limit)
- The result's `note` reports the total matches, how many remain after this page, and the offset to continue from

**Failure Handling:**
- Policy violation (path not in readable_paths) → Return `ToolFailure[T_tool]` with the error message identifying the violated policy.
- Invalid pattern (not a valid regex) → Return `ToolFailure[T_tool]` with the error message describing the pattern error.
- Invalid parameters (negative offset, zero limit, limit above the search result limit, or an omitted limit whose total matches exceed the search result limit) → Return `ToolFailure[T_tool]` with the error message describing the parameter error and advising offset/limit pagination.
- Filesystem errors are unhandled (no contract specified in this interface spec).

**HLS Justification:** search_files signals stubbing on duplicate search for the same path, pattern, offset, and limit.


### `read_chunks`

```python
def read_chunks(self, file_path: VirtualName, chunk_indices: list[int] | None = None, include_adjacent: bool = False) -> ToolCallOutcome
```

**Purpose:** Read semantic chunks from a Python file.

**Preconditions:**
- Python files must be accessible
- `file_path` must exist in `file_mappings` and be in `readable_paths`
- `file_path` must be a Python file
- `chunk_indices` if provided must contain valid non-negative indices

**Postconditions:**
- Returns chunk content with context in `content`
- If `chunk_indices` is `None`, returns all chunks (succeeds only when their total content fits within the read size limit, otherwise the call fails)
- `include_adjacent` includes neighboring chunks for context (adds the index of each requested chunk plus the indices of its immediate neighbors before and after)
- `content_id` is the virtual file path
- `stub_previous` per stubbing semantics (chunk overlap)
- The result's `note` reports which chunks were read, how many chunks remain, and the total content bytes

**Failure Handling:**
- Policy violation (path not a Python file, or not in readable_paths/file_mappings) → Return `ToolFailure[T_tool]` with the error message identifying the violated policy.
- Invalid parameters (non-negative chunk indices, or requested chunks whose total content exceeds the read size limit) → Return `ToolFailure[T_tool]` with the error message describing the parameter error and advising chunk_indices pagination.
- Filesystem errors are unhandled (no contract specified in this interface spec).

**HLS Justification:** read_chunks signals stubbing on chunk overlap for the same file.


### `replace_chunks`

```python
def replace_chunks(self, file_path: VirtualName, replacements: list[dict], encoding: str | None = None) -> ToolCallOutcome
```

**Purpose:** Replace multiple chunks in a Python file atomically.

**Preconditions:**
- Python files must be accessible
- `file_path` must exist in `file_mappings` and be in `writable_paths`
- `file_path` must be a Python file
- `replacements` must be a list of dicts, each containing `index: int` and `new_content: str`

**Postconditions:**
- All replacements apply atomically (all or nothing)
- File written with all replacements applied
- `write_occurred` flag set to `True`
- `content_id` is the virtual file path
- `stub_previous` is `True` (unconditional stubbing per stubbing semantics)
- Per-file stubbing state (read regions, chunk indices, search dedup records) for this file is cleared, so subsequent reads of the file will not be stubbed based on pre-write reads.
- The result is minimal: a structured success message (with counts where relevant); no file content is echoed

**Failure Handling:**
- Policy violation (path not a Python file, or not in writable_paths/file_mappings) → Return `ToolFailure[T_tool]` with the error message identifying the violated policy.
- Invalid arguments (each replacement dict must have `index` and `new_content`) → Return `ToolFailure[T_tool]` with the error message describing the argument error.
- Filesystem errors are unhandled (no contract specified in this interface spec).

**HLS Justification:** replace_chunks signals stubbing unconditionally for the file.


### `verify`

```python
def verify(self) -> ToolCallOutcome
```

**Purpose:** Report the run's file changes (diff vs. their state at run start); run the verification callback when one is configured and report its outcome.

**Preconditions:**
- None

**Postconditions:**
- Returns in `content` the diff of each changed file vs. its content at run start (per-file unified diffs), truncated when it exceeds the diff size limit; a truncated diff reports the truncated size and the full change counts
- When a verification callback is configured: additionally returns the callback's output string in `content`, followed by a note stating that `succeed` may now be called when the callback succeeded (exit 0), or that the reported issues must be fixed by changing files (`edit_file`/`replace_lines`/`write_file`) and then verifying again, or the agent may call `blame` or `fail` to end the run, when it failed; records the callback's success flag (this state gates `succeed`)
- When no verification callback is configured: appends a statement that no verification tool is present to validate the output and that `succeed` may now be called (verify has been called); records verify as called, satisfying the `succeed` gate
- `content_id` identifies the verification tool (e.g., "verify")
- `stub_previous` is `True` (unconditional stubbing per stubbing semantics)

**Failure Handling:**
- Callback throws exception → Callback error is unhandled (no contract specified in this interface spec).

**HLS Justification:** verify is always offered, signals stubbing unconditionally, reports the run's changes (diff, truncated at the diff size limit), and records the verification outcome that gates `succeed`.


### `succeed`

```python
def succeed(self, changes: list[dict[str, str]] = []) -> ToolCallOutcome
```

**Purpose:** Signal successful termination, carrying the agent's change summary. The agent calls this when it considers its task complete.

**Preconditions:**
- When the run changed files, `changes` must list one entry per changed file — `{"file": <virtual path>, "summary": <one short sentence on what changed, not how>}` — covering every changed file, each summary non-empty and within the summary length bound; the entries are broadcast to reverse dependencies to bring the next agent's attention to the changes
- When the run changed files, `verify` must have been called; when a verification callback is configured, its last outcome must have succeeded (exit 0); otherwise `succeed` signals a `ToolFailure` (the session continues)

**Postconditions:**
- Returns `TerminateAgentWithSuccess` (a `Signal[T_tool]` variant) carrying a `TerminateSuccessResult` describing the session outcome: no change if the run did not modify the workspace, or a change whose messages are built from `changes` (`"<file>: <summary>"` per entry) if it did
- No stubbing occurs (termination tools do not produce `ToolResult`)

**Failure Handling:**
- Verification gate unmet (run changed files and verify not called; or a callback is configured and verify not called or the last verify failed) → Return `ToolFailure[T_tool]` with a message distinguishing "verify() has not been called" from "the last verify() call failed" and advising the agent to verify (fixing any issues) or to call `fail`/`blame` to end the run.
- Run changed files and `changes` empty → Return `ToolFailure[T_tool]` listing the changed files and instructing the agent to call `succeed` again with one `{file, summary}` entry per changed file (one short sentence on what changed, not how) or to call `fail`/`blame` to end the run.
- An entry with a missing/empty `file` or `summary` → `ToolFailure[T_tool]` requiring both fields.
- An entry naming a file the run did not change → `ToolFailure[T_tool]` naming the changed files.
- A claimed change that does not appear in the diff — the file's current content equals its content at run start (rewritten with identical content) → `ToolFailure[T_tool]` stating the file is unchanged and advising the agent to report no change.
- A summary exceeding the length bound → `ToolFailure[T_tool]` asking for one short sentence.
- A changed file with no entry → `ToolFailure[T_tool]` listing the uncovered files.

**HLS Justification:** Termination tools signal termination when invoked correctly: the success operation signals successful termination carrying the agent's per-file change summary, gated on verify() having been called when the run changed files (and passed when a callback is configured), and requiring a change summary when the run changed files.


### `fail`

```python
def fail(self) -> ToolCallOutcome
```

**Purpose:** End the session in failure. The agent calls this when it considers the task cannot be completed.

**Postconditions:**
- Returns `TerminateAgentWithFailure[T_tool]` (a `Signal[T_tool]` variant); the session terminates in failure.
- A correctly-invoked `fail` is not a `ToolFailure` — `ToolFailure` signals a failed call.
- No stubbing occurs (termination tools do not produce `ToolResult`)

**HLS Justification:** Termination tools signal termination when invoked correctly: the failure operation ends the session in failure.


### `blame`

```python
def blame(self, blames: list[Blame]) -> ToolCallOutcome
```

**Purpose:** Signal termination with blame: attribute the task's incompleteness to dependencies and provide feedback on how to correct their outputs. The agent calls this when it considers the task incomplete and attributes the incompleteness to specific dependencies.

**Preconditions:**
- Blame targets are configured (non-empty)
- Each pair's target must be in `blame_targets`

**Postconditions:**
- If all pairs are valid: returns `TerminateAgentWithSuccess` (a `Signal[T_tool]` variant) carrying a `TerminateSuccessResult` that describes feedback to dependencies (one (target, feedback) pair per blamed dependency)
- If any pair's target is not in `blame_targets`: returns `ToolFailure[T_tool]` (a `Signal[T_tool]` variant)
- Each pair corresponds to one feedback message to its target
- No stubbing occurs (termination tools do not produce `ToolResult`)

**Failure Handling:**
- Invalid pairs (targets not in `blame_targets`): Return `ToolFailure[T_tool]` (a `Signal[T_tool]` variant) with an error message identifying the invalid pair.
- Empty `blames` list: Return `ToolFailure[T_tool]` with an error message describing the empty list.
- Blame targets not configured is a precondition violation (unexpected); the interface does not prescribe violation behavior (`blame` is not provided in the tool definitions when targets are empty).

**HLS Justification:** blame is a termination tool attributing incompleteness to dependencies.


### `get_write_occurred`

```python
def get_write_occurred(self) -> WriteOccurred
```

**Purpose:** Return whether the agent has modified the filesystem during the current run.

**Postconditions:** Returns `True` if any file write operation has succeeded during the current run; `False` otherwise.

**HLS Justification:** "The client may: Query whether the run has modified the filesystem."

## Invariants

- No state persists across runs
- Write-occurred flag is monotonic (once `True`, never `False`)
- All policy checks occur before any filesystem mutation
- `read_chunks` and `replace_chunks` operate only on Python files
- `verify` callback has no filesystem side effects
- Errors leave the filesystem unchanged
- Results with `content_id` `None` are never stubbed
- Stubbing preserves original message positions
- Termination tools never signal stubbing
- Successful writes clear per-file stubbing state (read regions, chunk indices, search dedup records), ensuring that subsequent reads of the written file are not stubbed based on pre-write reads
