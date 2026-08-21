<!-- Dependencies (md files to read alongside this one):
  - tool_provider-low.md
  - dag_storage-low.md
  - dag_clean_logic-low.md
  - agent_loop-low.md
-->

# Interface LLS: sandbox

## Data Types
```python
from typing import Any, Callable, Protocol, TypeVar, Generic, TypeAlias
from dataclasses import dataclass
from tool_provider import ToolDefinition, ToolResult, Signal, TerminateAgentWithSuccess, TerminateAgentWithFailure, TerminateSuccessResult, ToolFailure, ToolCallOutcome, T_tool

VirtualName: TypeAlias = str

FilePath: TypeAlias = str

FileMapping: TypeAlias = dict[VirtualName, FilePath]

ReadablePaths: TypeAlias = list[VirtualName]

WritablePaths: TypeAlias = list[VirtualName]

BlameTargets: TypeAlias = list[str]

BlameTarget: TypeAlias = str

Feedback: TypeAlias = str

Blame: TypeAlias = tuple[BlameTarget, Feedback]

SearchResultLimit: TypeAlias = int

DiffSizeLimit: TypeAlias = int

VerificationCallback: TypeAlias = Callable[[], tuple[bool, str]] | None

@dataclass
class SandboxConfig:
    file_mappings: FileMapping
    readable_paths: ReadablePaths
    writable_paths: WritablePaths
    blame_targets: BlameTargets
    search_result_limit: SearchResultLimit
    diff_size_limit: DiffSizeLimit | None = None
    verification_callback: VerificationCallback = None

WriteOccurred: TypeAlias = bool

class Sandbox(Protocol):
    def get_tool_definitions(self) -> list[ToolDefinition]: ...
    def read_file(self, file_path: VirtualName, include_line_numbers: bool = False) -> ToolCallOutcome: ...
    def write_file(self, file_path: VirtualName, content: str) -> ToolCallOutcome: ...
    def edit_file(self, file_path: VirtualName, old_str: str, new_str: str, expect_multiple: bool = False) -> ToolCallOutcome: ...
    def replace_lines(self, file_path: VirtualName, start_line: int, end_line: int, new_str: str) -> ToolCallOutcome: ...
    def search_files(self, path: VirtualName, pattern: str, offset: int | None = None, limit: int | None = None) -> ToolCallOutcome: ...
    def verify(self) -> ToolCallOutcome: ...
    def succeed(self, changes: list[dict[str, str]] = []) -> ToolCallOutcome: ...
    def fail(self) -> ToolCallOutcome: ...
    def blame(self, blames: list[Blame]) -> ToolCallOutcome: ...
    def get_write_occurred(self) -> WriteOccurred: ...
```

`BlameTarget` identifies a node the agent may blame (a dependency of the current run). `Feedback` is the correction feedback on how to correct the blamed node's output. Each `Blame` pair corresponds to one feedback message to its target.

The client-supplied configuration for a sandbox: file mappings, readable and writable paths, blame targets, the search result limit and the diff size limit, and an optional verification callback.
## Stubbing (term definition)

These rules apply to all sandbox operations that produce a `ToolResult`.

- A `ToolResult`'s `supersedes` flag is set on the results of operations on writable files and on verification results; it is not set on reads of files that are not writable, on `search_files`, or on termination tools' results.
- A `read_file` of a writable file sets the flag: it supersedes the earlier non-stubbed result for that file, and always provides the file's entire content.
- A `write_file`, `edit_file`, or `replace_lines` result sets the flag: it supersedes the earlier non-stubbed result for that file; the result's content is the operation's status, never a file-content echo.
- A `verify` result sets the flag: it supersedes the earlier non-stubbed verification result.
- The superseded result is identified by the file's virtual name (file operations) or the verification tool's name (`"verify"`) — the name the operation itself carries; no separate identity is introduced. At most one non-stubbed result exists per file or per the verification command at any time, so a result supersedes at most one earlier result.
- A file's view: each writable file has a view for the run — plain or line-numbered. A writable file that already exists on disk is only readable in the line-numbered view (a plain read fails advising the line-numbered view), so its view is line-numbered from its first successful read; a new file's results render plain until the agent reads it in the line-numbered view. A write resets the view to plain — the line numbers are invalidated by the write — so a line-range edit after a write requires a fresh numbered read (a read with `include_line_numbers=True` re-enables the view).
- After a successful `write_file`, `edit_file`, or `replace_lines`, the file's earlier results are superseded (stubbed by the consuming agent loop), so the file's current content is not visible in the conversation until the agent reads the file again.
- A `replace_lines` failure for a file whose view is not line-numbered returns `ToolFailure[T_tool]` with a message advising `read_file(file_path, include_line_numbers=True)`; the failure supersedes nothing and removes nothing.
- Search suppression: `search_files` renders matches only for files that are not writable; matches in writable files are reported as counts without content, so search results never become stale.
- Notes: every successful read and search carries a note reporting what was returned; write and edit notes report the operation's status; the verification note reports only whether verification succeeded or failed (or that no verification tool is configured), never the failure details themselves, which live in the result's content. A tool result never carries the stub text.

## Component-Provided Operations

### `get_tool_definitions`

```python
def get_tool_definitions(self) -> list[ToolDefinition]
```

**Purpose:** Return the list of tool definitions available in the current sandbox configuration. Tools are conditionally included based on the configuration provided at initialization.

**Preconditions:** The sandbox has been configured with file mappings, readable/writable paths, and optional verification callback.

**Postconditions:** Returns a list of tool definitions. Each definition follows the JSON schema format expected by the model (as defined in `tool_provider`). The following tools are included:
- `read_file`, `write_file`, `edit_file`, `replace_lines`, `search_files`, `verify` (always)
- `succeed`, `fail` (always)
- `blame` only if blame targets are non-empty

**Failure Handling:** No failure conditions.

**HLS Justification:** "The sandbox provides tool definitions that the agent loop can pass to the model."


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
- When `include_line_numbers` is `True`: each line is prefixed with its 1-indexed line number (`"N \u2502 line"`); the file's view for the run becomes line-numbered
- When `include_line_numbers` is `False` (a non-writable file): lines are returned without prefixes
- `supersedes` is `True` when `file_path` is in `writable_paths` (the result supersedes the earlier result for that file) and `False` when `file_path` is not in `writable_paths`
- `content` is the file's content in the file's current view
- The result's `note` reports the file's line count and view

**Failure Handling:**
- Policy violation (file_path not in readable_paths or file_mappings) → Return `ToolFailure[T_tool]` with the error message identifying the violated policy.
- Invalid parameters (`include_line_numbers` requested for a non-writable file) → Return `ToolFailure[T_tool]` with the error message describing the parameter error.
- Writable file already exists and `include_line_numbers` is `False` → Return `ToolFailure[T_tool]` advising the agent to call `read_file` with `include_line_numbers=True` (line numbers are metadata, never file content).
- Filesystem errors are unhandled (no contract specified in this interface spec).

**HLS Justification:** read_file reads the entire file; a writable-file read supersedes the file's earlier result, keeping the conversation current.


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
- The outcome is a `ToolResult` with `supersedes` set to `True` (it supersedes the earlier result for that file)
- The result's `content` and `note` are minimal: a structured success message (with counts where relevant); no file content is echoed in the conversation

**Failure Handling:**
- Policy violation (file_path not in writable_paths or file_mappings) → Return `ToolFailure[T_tool]` with the error message identifying the violated policy.
- Invalid arguments (non-empty content required) → Return `ToolFailure[T_tool]` with the error message describing the argument error.
- File already exists → Return `ToolFailure[T_tool]` stating that write_file is only for creating new files and advising `edit_file` (content-based) or `replace_lines` (line-based).
- Filesystem errors are unhandled (no contract specified in this interface spec).

**HLS Justification:** write_file is a file write: it modifies the filesystem and supersedes the file's earlier results.


### `edit_file`

```python
def edit_file(self, file_path: VirtualName, old_str: str, new_str: str,
              expect_multiple: bool = False) -> ToolCallOutcome
```

**Purpose:** Replace text in a file by content-based search and replace.

**Preconditions:**
- `file_path` must exist in `file_mappings` and be in `writable_paths`
- `old_str` must be non-empty and at most 100 characters; `new_str` must be at most 100 characters (edit_file is for short search/replace pairs; whole-file and large edits go through `replace_lines`)
- The file must exist on disk (edits modify existing files; use `write_file` to create new ones)

**Postconditions:**
- When `expect_multiple` is `False`: exactly one occurrence of `old_str` is replaced with `new_str`; when `True`: every occurrence is replaced
- The file is written with the replacement applied; `write_occurred` flag set to `True`
- The outcome is a `ToolResult` with `supersedes` set to `True` (it supersedes the earlier result for that file)
- The result's `content` and `note` are minimal: a structured success message (with counts where relevant); no file content is echoed in the conversation

**Failure Handling:**
- Policy violation (file_path not in writable_paths or file_mappings) → Return `ToolFailure[T_tool]` with the error message identifying the violated policy.
- Invalid arguments (empty `old_str`; `old_str` identical to `new_str` — the edit would change nothing; `old_str` or `new_str` exceeding 100 characters) → Return `ToolFailure[T_tool]` with the error message describing the argument error; an over-length string error advises `replace_lines` (which requires the line-numbered view).
- `old_str` absent from the file → Return `ToolFailure[T_tool]` stating it was not found.
- More than one match with `expect_multiple` `False` → Return `ToolFailure[T_tool]` stating the match count and advising `expect_multiple=True` or a narrower `old_str`.
- Filesystem errors are unhandled (no contract specified in this interface spec).

**HLS Justification:** edit_file is a file write: it modifies the filesystem and supersedes the file's earlier results.


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
- The file must exist on disk (edits modify existing files; use `write_file` to create new ones)
- The file's current view must be line-numbered, and the file must have been read in the line-numbered view since the last write (a write resets the view to plain; see Result Routing)

**Postconditions:**
- Lines `start_line` through `end_line` (inclusive) are replaced with `new_str`; `start_line > end_line` inserts `new_str` before line `start_line` (no lines removed); empty `new_str` deletes the range; a trailing newline is preserved when the file had one and lines remain
- The file is written with the change applied; `write_occurred` flag set to `True`
- The outcome is a `ToolResult` with `supersedes` set to `True` (it supersedes the earlier result for that file)
- The result's `content` and `note` are minimal: a structured success message (with counts where relevant); no file content is echoed in the conversation

**Failure Handling:**
- Policy violation (file_path not in writable_paths or file_mappings) → Return `ToolFailure[T_tool]` with the error message identifying the violated policy.
- The file's current view is not line-numbered → Return `ToolFailure[T_tool]` advising `read_file(file_path, include_line_numbers=True)` before editing and noting that a write invalidated the line numbers when the view became plain due to a write; the failure supersedes nothing and removes nothing.
- Invalid arguments (non-integer line numbers, or `start_line`/`end_line` out of bounds) → Return `ToolFailure[T_tool]` with the error message describing the argument error and the file's line count.
- Filesystem errors are unhandled (no contract specified in this interface spec).

**HLS Justification:** replace_lines is a file write: it requires the line-numbered view and supersedes the file's earlier results.


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

**HLS Justification:** search_files renders matches only for files that are not writable, so its results never become stale.


### `verify`

```python
def verify(self) -> ToolCallOutcome
```

**Purpose:** Report the run's file changes (diff vs. their state at run start); run the verification callback when one is configured and report its outcome.

**Preconditions:**
- None

**Postconditions:**
- The outcome is a `ToolResult` with `supersedes` set to `True` (it supersedes the earlier non-stubbed verification result)
- `content` holds the verification report; the result's `note` reports only whether verification succeeded or failed (or that no verification tool is configured) and never carries the failure details, which live in `content`
- The verification report contains the diff of each changed file vs. its content at run start (per-file unified diffs), truncated when it exceeds the diff size limit; a truncated diff reports the truncated size and the full change counts
- When a verification callback is configured: the report additionally contains the callback's output string, followed by a statement that `succeed` may now be called when the callback succeeded (exit 0), or that the reported issues must be fixed by changing files (`edit_file`/`replace_lines`/`write_file`) and then verifying again, or the agent may call `blame` or `fail` to end the run, when it failed; the callback's success flag is recorded (this state gates `succeed`)
- When no verification callback is configured: the report states that no verification tool is present to validate the output and that `succeed` may now be called (verify has been called); verify is recorded as called, satisfying the `succeed` gate

**Failure Handling:**
- Callback throws exception → Callback error is unhandled (no contract specified in this interface spec).

**HLS Justification:** verify is always offered, supersedes the earlier verification result, reports the run's changes (diff, truncated at the diff size limit), and records the verification outcome that gates `succeed`.


### `succeed`

```python
def succeed(self, changes: list[dict[str, str]] = []) -> ToolCallOutcome
```

**Purpose:** Signal successful termination, carrying the agent's change summary. The agent calls this when it considers its task complete.

**Preconditions:**
- A file counts as changed only when its current content differs from its content at run start (a write that nets out to no change — e.g., an edit later undone — is not changed)
- When the run changed files, `changes` must list one entry per changed file — `{"file": <virtual path>, "summary": <one short sentence naming the parts of the file that changed, so the next reader knows what to pay attention to when updating further artifacts; not the task performed, not how it was done>}` — covering every changed file, each summary non-empty and within the hard length bound; the entries are broadcast to reverse dependencies to bring the next reader's attention to the changes
- A summary within the soft length bound is accepted; a summary within the hard length bound is accepted once the soft-limit grace has been exhausted; the grace counts rejections per run (the soft-limit grace and the hard-limit grace are independent)
- When the run changed files, `verify` must have been called; when a verification callback is configured, its last outcome must have succeeded (exit 0); otherwise `succeed` signals a `ToolFailure` (the session continues)

**Postconditions:**
- Returns `TerminateAgentWithSuccess` (a `Signal[T_tool]` variant) carrying a `TerminateSuccessResult` describing the session outcome: no change when no file's current content differs from its run-start content (writes may have occurred but net out), or a change whose messages are built from `changes` (`"<file>: <summary>"` per entry) when files changed
- Termination tools produce no `ToolResult` and never supersede an earlier result

**Failure Handling:**
- Verification gate unmet (run changed files and verify not called; or a callback is configured and verify not called or the last verify failed) → Return `ToolFailure[T_tool]` with a message distinguishing "verify() has not been called" from "the last verify() call failed" and advising the agent to verify (fixing any issues) or to call `fail`/`blame` to end the run.
- Run changed files and `changes` empty → Return `ToolFailure[T_tool]` listing the changed files and instructing the agent to call `succeed` again with one `{file, summary}` entry per changed file (one short sentence on what changed, not how) or to call `fail`/`blame` to end the run.
- An entry with a missing/empty `file` or `summary` → `ToolFailure[T_tool]` requiring both fields.
- An entry naming a file the run did not change → `ToolFailure[T_tool]` naming the changed files.
- A claimed change for a run whose writes all net out to no change (every written file's current content equals its run-start content) → `ToolFailure[T_tool]` stating the run net-changed nothing and directing `succeed()` with no changes to report no change.
- A summary exceeding the soft length bound (within the hard bound) before the soft-limit grace is exhausted → `ToolFailure[T_tool]` directing the agent to shorten the summary to at most the soft bound: one short sentence naming the parts of the file that changed for the next reader, dropping how it was done, then call `succeed` again; once the soft-limit grace (4 rejections per run) is exhausted, such a summary is accepted.
- A summary exceeding the hard length bound before the hard-limit grace is exhausted → `ToolFailure[T_tool]` naming the hard bound and directing the agent to shorten the summary to at most the hard bound; once the hard-limit grace (4 rejections per run) is exhausted, a summary still exceeding the hard bound turns `succeed` into a hard failure: return `TerminateAgentWithFailure[T_tool]` ending the run in failure.
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
- Termination tools produce no `ToolResult` and never supersede an earlier result

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
- Termination tools produce no `ToolResult` and never supersede an earlier result

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

- The run begins when the sandbox is configured and ends when the agent signals termination
- No state persists across runs
- Write-occurred flag is monotonic (once `True`, never `False`)
- All policy checks occur before any filesystem mutation
- `verify` callback has no filesystem side effects
- Errors leave the filesystem unchanged
- A result with `supersedes` set supersedes the earlier non-stubbed result for the same file or tool command; a result with `supersedes` unset supersedes nothing
- A result supersedes at most one earlier result (at most one non-stubbed result exists per file or per the verification command at any time)
- A write or edit supersedes the file's earlier results, so the file's current content is not visible until the agent reads the file again
- An edit's replacement applies atomically (all or nothing): a replacement is never partially applied
- `replace_lines` requires the line-numbered view
- Termination tools never produce `ToolResult` and never supersede an earlier result
- Search results never render matches from writable files
- A tool result never carries the stub text
