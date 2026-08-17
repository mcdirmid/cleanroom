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
VerificationCallback = Callable[[], str] | None
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
    verification_callback: VerificationCallback = None
```

The client-supplied configuration for a sandbox: file mappings, readable and writable paths, blame targets, read size and search result limits, and an optional verification callback.

```python
WriteOccurred = bool
```

```python
class Sandbox(Protocol):
    def get_tool_definitions(self) -> list[ToolDefinition]: ...
    def read_file(self, file_path: VirtualName, offset: int | None = None, limit: int | None = None) -> ToolCallOutcome: ...
    def write_file(self, file_path: VirtualName, content: str) -> ToolCallOutcome: ...
    def search_files(self, path: VirtualName, pattern: str) -> ToolCallOutcome: ...
    def read_chunks(self, file_path: VirtualName, chunk_indices: list[int] | None = None, include_adjacent: bool = False) -> ToolCallOutcome: ...
    def replace_chunks(self, file_path: VirtualName, replacements: list[dict], encoding: str | None = None) -> ToolCallOutcome: ...
    def verify(self) -> ToolCallOutcome: ...
    def succeed(self) -> ToolCallOutcome: ...
    def fail(self) -> ToolCallOutcome: ...
    def blame(self, blames: list[Blame]) -> ToolCallOutcome: ...
    def get_write_occurred(self) -> WriteOccurred: ...
```

## Stubbing Semantics (term definition)

These rules apply to all sandbox operations that produce a `ToolResult` (i.e., when the `ToolCallOutcome` is a `ToolResult`).

- Read-file region overlap (read_file): A read region is the byte range actually read from the file: from the starting offset through the last byte returned (a read truncated at end-of-file records the region ending at the end of the returned content, not the requested limit). Two regions overlap if they share any byte position. `stub_previous` is `True` if the current region overlaps with any previous non-stubbed region for the same file.
- Chunk overlap (read_chunks): `stub_previous` is `True` if the chunk indices whose content is returned (the requested indices plus any adjacent context included via `include_adjacent`) overlap with any previous non-stubbed chunk reads for the same file.
- Search dedup (search_files): `stub_previous` is `True` if the same `path` and `pattern` were previously searched.
- Unconditional stubbing: `write_file`, `replace_chunks`, and `verify` always set `stub_previous=True`. Termination tools (`succeed`, `fail`, `blame`) never stub (`content_id` is `None`).
- Stub replacement text: stubbed content is replaced with a placeholder that clearly indicates removal (the exact placeholder text is pinned in the implementation spec). Stubbed messages retain their original position in the conversation.
- Write-side effects on stubbing state: `write_file` and `replace_chunks` clear the per-file stubbing state (read regions, chunk indices, search dedup records) after a successful write.

## Component-Provided Operations

### `get_tool_definitions`

```python
def get_tool_definitions(self) -> list[ToolDefinition]
```

**Purpose:** Return the list of tool definitions available in the current sandbox configuration. Tools are conditionally included based on the configuration provided at initialization.

**Preconditions:** The sandbox has been configured with file mappings, readable/writable paths, and optional verification callback.

**Postconditions:** Returns a list of tool definitions. Each definition follows the JSON schema format expected by the model (as defined in `tool_provider`). The following tools are included:
- `read_file`, `write_file`, `search_files` (always)
- `read_chunks`, `replace_chunks` only if Python files are accessible
- `verify` only if verification callback is non-null
- `succeed`, `fail` (always)
- `blame` only if blame targets are non-empty

**Failure Handling:** No failure conditions.

**HLS Justification:** "The sandbox provides tool definitions that the agent loop can pass to the model."


### `read_file`

```python
def read_file(self, file_path: VirtualName, offset: int | None = None, limit: int | None = None) -> ToolCallOutcome
```

**Purpose:** Read content from a file using the virtual name provided by the agent.

**Preconditions:**
- `file_path` must exist in `file_mappings` and be in `readable_paths`
- If `offset` provided, must be non-negative
- If `limit` provided, must be positive

**Postconditions:**
- Returns file content as string in `content`
- If `offset` not provided, starts from beginning (0)
- If `limit` not provided, reads up to `read_size_limit` bytes
- `content_id` is the virtual file path
- `stub_previous` per stubbing semantics (read-file region overlap)

**Failure Handling:**
- Policy violation (file_path not in readable_paths or file_mappings) → Return `ToolFailure[T_tool]` with the error message identifying the violated policy.
- Invalid parameters (negative offset, zero limit) → Return `ToolFailure[T_tool]` with the error message describing the parameter error.
- Filesystem errors are unhandled (no contract specified in this interface spec).

**HLS Justification:** read_file signals stubbing on read-region overlap for the same file.


### `write_file`

```python
def write_file(self, file_path: VirtualName, content: str) -> ToolCallOutcome
```

**Purpose:** Write content to a file using the virtual name provided by the agent.

**Preconditions:**
- `file_path` must exist in `file_mappings` and be in `writable_paths`
- Content must be non-empty

**Postconditions:**
- File is written at the resolved path (overwrites)
- `write_occurred` flag set to `True`
- `content_id` is the virtual file path
- `stub_previous` is `True` (unconditional stubbing per stubbing semantics)
- Per-file stubbing state (read regions, chunk indices, search dedup records) for this file is cleared, so subsequent reads of the file will not be stubbed based on pre-write reads.

**Failure Handling:**
- Policy violation (file_path not in writable_paths or file_mappings) → Return `ToolFailure[T_tool]` with the error message identifying the violated policy.
- Invalid arguments (non-empty content required) → Return `ToolFailure[T_tool]` with the error message describing the argument error.
- Filesystem errors are unhandled (no contract specified in this interface spec).

**HLS Justification:** write_file signals stubbing unconditionally for the file.


### `search_files`

```python
def search_files(self, path: VirtualName, pattern: str) -> ToolCallOutcome
```

**Purpose:** Search for a pattern in files using the virtual path provided by the agent.

**Preconditions:**
- `path` must be in `readable_paths`
- `pattern` must be a valid regex pattern

**Postconditions:**
- Returns search results as string in `content`
- Results limited to `search_result_limit` entries
- Searches recursively within the specified path
- `content_id` is the virtual path
- `stub_previous` per stubbing semantics (search dedup)

**Failure Handling:**
- Policy violation (path not in readable_paths) → Return `ToolFailure[T_tool]` with the error message identifying the violated policy.
- Invalid pattern (not a valid regex) → Return `ToolFailure[T_tool]` with the error message describing the pattern error.
- Filesystem errors are unhandled (no contract specified in this interface spec).

**HLS Justification:** search_files signals stubbing on duplicate search for the same path and pattern.


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
- If `chunk_indices` is `None`, returns all chunks
- `include_adjacent` includes neighboring chunks for context (adds the index of each requested chunk plus the indices of its immediate neighbors before and after)
- `content_id` is the virtual file path
- `stub_previous` per stubbing semantics (chunk overlap)

**Failure Handling:**
- Policy violation (path not a Python file, or not in readable_paths/file_mappings) → Return `ToolFailure[T_tool]` with the error message identifying the violated policy.
- Invalid parameters (non-negative chunk indices) → Return `ToolFailure[T_tool]` with the error message describing the parameter error.
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

**Failure Handling:**
- Policy violation (path not a Python file, or not in writable_paths/file_mappings) → Return `ToolFailure[T_tool]` with the error message identifying the violated policy.
- Invalid arguments (each replacement dict must have `index` and `new_content`) → Return `ToolFailure[T_tool]` with the error message describing the argument error.
- Filesystem errors are unhandled (no contract specified in this interface spec).

**HLS Justification:** replace_chunks signals stubbing unconditionally for the file.


### `verify`

```python
def verify(self) -> ToolCallOutcome
```

**Purpose:** Run the verification callback.

**Preconditions:**
- Verification callback must be non-null

**Postconditions:**
- Returns callback string in `content`, without modification
- `content_id` identifies the verification tool (e.g., "verify")
- `stub_previous` is `True` (unconditional stubbing per stubbing semantics)

**Failure Handling:**
- Callback null is a precondition violation (unexpected); the interface does not prescribe violation behavior.
- Callback throws exception → Callback error is unhandled (no contract specified in this interface spec).

**HLS Justification:** verify (when configured) signals stubbing unconditionally.


### `succeed`

```python
def succeed(self) -> ToolCallOutcome
```

**Purpose:** Signal successful termination. The agent calls this when it considers its task complete.

**Postconditions:**
- Returns `TerminateAgentWithSuccess` (a `Signal[T_tool]` variant) carrying a `TerminateSuccessResult` describing the session outcome: no change if the run did not modify the workspace, or changes to propagate if it did (the implementation forms the result)
- No stubbing occurs (termination tools do not produce `ToolResult`)

**HLS Justification:** Termination tools signal termination when invoked correctly: the success operation signals successful termination.


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
