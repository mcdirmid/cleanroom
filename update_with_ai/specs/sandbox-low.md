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
from dataclasses import dataclass, field
from tool_provider import ToolDefinition, ToolResult, PresentedToolResult, Signal, TerminateAgentWithSuccess, TerminateAgentWithFailure, TerminateSuccessResult, ToolFailure, ToolCallOutcome, T_tool

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

TemplateMapping: TypeAlias = dict[VirtualName, str]

VerificationCallback: TypeAlias = Callable[[], tuple[bool, str]] | None

@dataclass
class SandboxConfig:
    file_mappings: FileMapping
    readable_paths: ReadablePaths
    writable_paths: WritablePaths
    blame_targets: BlameTargets
    search_result_limit: SearchResultLimit
    diff_size_limit: DiffSizeLimit | None = None
    session_start_reads_enabled: bool = True
    guide: VirtualName | None = None
    step_sections_enabled: bool = True
    templates: TemplateMapping = field(default_factory=dict)
    verification_callback: VerificationCallback = None

WriteOccurred: TypeAlias = bool

class Sandbox(Protocol):
    def get_tool_definitions(self) -> list[ToolDefinition]: ...
    def get_session_start_reads(self) -> list[PresentedToolResult]: ...
    def read_file(self, file_path: VirtualName, include_line_numbers: bool = False) -> ToolCallOutcome: ...
    def edit_file(self, file_path: VirtualName, old_str: str, new_str: str, expect_multiple: bool = False) -> ToolCallOutcome: ...
    def replace_lines(self, file_path: VirtualName, start_line: int, end_line: int, new_str: str) -> ToolCallOutcome: ...
    def search_files(self, path: VirtualName, pattern: str, offset: int | None = None, limit: int | None = None) -> ToolCallOutcome: ...
    def advance(self, changes: list[dict[str, str]] = []) -> ToolCallOutcome: ...
    def fail(self) -> ToolCallOutcome: ...
    def blame(self, blames: list[Blame]) -> ToolCallOutcome: ...
    def get_write_occurred(self) -> WriteOccurred: ...
```

`BlameTarget` identifies a node the agent may blame (a dependency of the current run). `Feedback` is the correction feedback on how to correct the blamed node's output. Each `Blame` pair corresponds to one feedback message to its target.

The client-supplied configuration for a sandbox: file mappings, readable and writable paths, blame targets, the search result limit and the diff size limit, whether session-start reads are enabled (default: enabled), the guide (default: none — the declared guide's virtual name, a file in `file_mappings`), whether step mode is enabled (default: enabled), the templates (default: empty), and an optional verification callback.
## Stubbing (term definition)

These rules apply to all sandbox operations that produce a `ToolResult`.

- Stubbing follows `tool_provider` semantics: when a result's `supersedes` flag is set, the earlier non-stubbed result for the same file or tool command is replaced by a placeholder, keeping the conversation focused on current state; a result with the flag unset supersedes nothing, and at most one earlier result is superseded per result.

## Auto re-read (term definition)

These rules apply to the outcome of a successful `edit_file` or `replace_lines`.

- After a successful `edit_file` or `replace_lines`, the file's current content appears in the conversation.
- A write that fails does not provide the file's content.

## Session-start reads (term definition)

These rules apply to the reads provided at the beginning of a run.

- When `session_start_reads_enabled` is set, a session-start read is provided for every file in `readable_paths` that is not in `writable_paths`; when unset, none are provided.
- Session-start reads are provided in a deterministic order (sorted by virtual name).
- A session-start read renders the file's content plain and never supersedes an earlier result.
- In step mode, the guide is not among the session-start reads: its content reaches the agent only through `advance`'s outputs (per the Step mode rules).

## Step mode (term definition)

These rules apply when `step_sections_enabled` is set and `guide` is configured; the guide is a readable file in the guide format — its first line is `# Guide: <title>` and its first `##` heading is `## Summary`.

- In step mode, the guide is not readable: `read_file` of the guide returns `ToolFailure` identifying the violated policy; the guide is never provided whole; its content reaches the agent only through `advance`'s outputs.
- In step mode, the guide is revealed incrementally: `advance` delivers one section at a time.
- The run cannot terminate until all guide sections are delivered and verification passes.
- A failing verification prevents progressing to the next section, requiring correction before continuing.
- A readable file that is not the guide is unaffected by step mode.
- When step mode is disabled, the guide is provided whole at run start (a session-start read, per the Session-start reads rules) and is re-readable like other readable files.

## Template initialization (term definition)

These rules apply to the files created from configured templates at the beginning of a run.

- `templates` maps a writable file's virtual name to its template content: the initial content configured for the file.
- Files with templates are initialized from their template content at run start.
- A writable file that exists when the sandbox is configured is never modified by its template.
- Template initialization is not a run write: it never sets the write-occurred flag and never records the file as changed.

## Component-Provided Operations

### `get_tool_definitions`

```python
def get_tool_definitions(self) -> list[ToolDefinition]
```

**Purpose:** Return the list of tool definitions available in the current sandbox configuration. Tools are conditionally included based on the configuration provided at initialization.

**Preconditions:** The sandbox has been configured with file mappings, readable/writable paths, and optional verification callback.

**Postconditions:** Returns a list of tool definitions. Each definition follows the JSON schema format expected by the model (as defined in `tool_provider`). The following tools are included:
- `read_file`, `edit_file`, `replace_lines`, `search_files`, `advance` (always)
- `fail` (always)
- `blame` only if blame targets are non-empty

**Failure Handling:** No failure conditions.

**HLS Justification:** "The sandbox provides tool definitions that the agent loop can pass to the model."


### `get_session_start_reads`

```python
def get_session_start_reads(self) -> list[PresentedToolResult]
```

**Purpose:** Return the session-start reads: the plain reads of the read-only files, for rendering at the beginning of a run before the model's first turn.

**Preconditions:** None.

**Postconditions:**
- When `session_start_reads_enabled` is set: returns a session-start read (per the Session-start reads rules) for every file in `readable_paths` that is not in `writable_paths`, sorted by virtual name
- When `session_start_reads_enabled` is unset: returns an empty list
- In step mode, the guide is not among the reads (per the Step mode rules)
- Each session-start read is a `PresentedToolResult` pairing the `read_file` call with its plain read result; each result's `supersedes` is unset
- Requesting the session-start reads changes no sandbox state

**Failure Handling:** Always succeeds; filesystem errors reading a readable file are unhandled.

**HLS Justification:** "The client may: Request the session-start reads."


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
- The file is written with the replacement applied; `write_occurred` flag set to `True`
- The outcome is a sequence of two results, per the Auto re-read rules: a write confirmation (a `ToolResult` with `supersedes` set to `True`; it supersedes the earlier result for that file) and an injected read
- The write confirmation's `content` and `note` are minimal: a structured success message (with counts where relevant); no file content is echoed in it

**Failure Handling:**
- Policy violation (file_path not in writable_paths or file_mappings) → Return `ToolFailure[T_tool]` with the error message identifying the violated policy.
- Invalid arguments (empty `old_str`; `old_str` identical to `new_str` — the edit would change nothing; `old_str` or `new_str` exceeding 100 characters) → Return `ToolFailure[T_tool]` with the error message describing the argument error; an over-length string error advises `replace_lines` (which requires the line-numbered view).
- `old_str` absent from the file → Return `ToolFailure[T_tool]` stating it was not found.
- More than one match with `expect_multiple` `False` → Return `ToolFailure[T_tool]` stating the match count and advising `expect_multiple=True` or a narrower `old_str`.
- Filesystem errors are unhandled (no contract specified in this interface spec).

**HLS Justification:** edit_file is a file write: it modifies the filesystem, supersedes the file's earlier results, and provides an injected read.


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
- The file is written with the change applied; `write_occurred` flag set to `True`
- The outcome is a sequence of two results, per the Auto re-read rules: a write confirmation (a `ToolResult` with `supersedes` set to `True`; it supersedes the earlier result for that file) and an injected read
- The write confirmation's `content` and `note` are minimal: a structured success message (with counts where relevant); no file content is echoed in it

**Failure Handling:**
- Policy violation (file_path not in writable_paths or file_mappings) → Return `ToolFailure[T_tool]` with the error message identifying the violated policy.
- The file's current view is not line-numbered → Return `ToolFailure[T_tool]` advising `read_file(file_path, include_line_numbers=True)` before editing and noting that a write invalidated the line numbers when the view became plain due to a write; the failure supersedes nothing and removes nothing.
- Invalid arguments (non-integer line numbers, or `start_line`/`end_line` out of bounds) → Return `ToolFailure[T_tool]` with the error message describing the argument error and the file's line count.
- Filesystem errors are unhandled (no contract specified in this interface spec).

**HLS Justification:** replace_lines is a file write: it requires the line-numbered view, supersedes the file's earlier results, and provides an injected read.


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


### `advance`

```python
def advance(self, changes: list[dict[str, str]] = []) -> ToolCallOutcome
```

**Purpose:** Signal the run's completion: advance signals successful termination when verification passes, or provides feedback on a failing verification; in step mode, advance delivers the guide one section at a time until the guide is consumed. The agent calls this when it has nothing more to do or considers its task complete.

**Preconditions:**
- A file counts as changed only when its current content differs from its content at run start (a write that nets out to no change — e.g., an edit later undone — is not changed)
- The change-message requirement applies only to the terminating advance: in step mode, an advance with step sections remaining carries no change message
- When the run changed files, `changes` must list one entry per changed file — `{"file": <virtual path>, "summary": <one short sentence naming the parts of the file that changed for the next reader; not the task performed, not how it was done>}` — covering every changed file, each summary non-empty and within the summary bound
- A summary exceeding the summary bound is rejected with guidance to shorten it; persistent rejection fails the run

**Postconditions:**
- Verifies the run: runs the verification callback when one is configured; when no callback is configured, verification is treated as passed
- On a failing verification: returns a `ToolResult` providing feedback — the verification failure details and guidance to change files and call `advance` again, or call `blame` or `fail` to end the run; the session continues and advance never terminates on a failing verification
- On a passing verification (or no callback): returns `TerminateAgentWithSuccess` (a `Signal[T_tool]` variant) carrying a `TerminateSuccessResult` describing the session outcome: no change when no file's current content differs from its run-start content (writes may have occurred but net out), or a change whose messages are built from `changes` when files changed
- In step mode: on a passing verification with step sections remaining, returns the next step section; on a failing verification, returns the guide summary with the reason verification failed, and the next section is not delivered (per the Step mode rules); on a passing verification with no step sections remaining, proceeds to termination
- Termination tools produce no `ToolResult` and never supersede an earlier result; advance's termination outcome is never a tool failure; the change-message machinery (including the empty-message failure) applies only to the terminating advance

**Failure Handling:**
- In step mode, an advance with step sections remaining never signals a tool failure for the change message: the change-message machinery applies only to the terminating advance.
- Run changed files and `changes` empty → Return `ToolFailure[T_tool]` listing the changed files and instructing the agent to call `advance` again with one `{file, summary}` entry per changed file (one short sentence on what changed, not how) or to call `fail`/`blame` to end the run.
- An entry with a missing/empty `file` or `summary` → `ToolFailure[T_tool]` requiring both fields.
- An entry naming a file the run did not change → `ToolFailure[T_tool]` naming the changed files.
- A claimed change for a run whose writes all net out to no change (every written file's current content equals its run-start content) → `ToolFailure[T_tool]` stating the run net-changed nothing and directing `advance()` with no changes to report no change.
- A summary exceeding the summary bound → `ToolFailure[T_tool]` directing the agent to shorten the summary and call `advance` again; persistent rejection turns `advance` into failure.
- A changed file with no entry → `ToolFailure[T_tool]` listing the uncovered files.
- Verification callback throws exception → Callback error is unhandled (no contract specified in this interface spec).

**HLS Justification:** advance signals successful termination when verification passes, provides feedback (never a tool failure) on a failing verification, and requires a change summary when the run changed files.


### `fail`

```python
def fail(self) -> ToolCallOutcome
```

**Purpose:** End the session in failure. The agent calls this when it considers the task cannot be completed.

**Preconditions:** No termination signal has been produced yet in the current session.

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

**Preconditions:** None.

**Postconditions:** Returns `True` if any file write operation has succeeded during the current run; `False` otherwise.

**HLS Justification:** "The client may: Query whether the run has modified the filesystem."

## Invariants

- The run begins when the sandbox is configured and ends when the agent signals termination
- Every `templates` entry names a writable file (a virtual name in `writable_paths`)
- The guide, when configured, names a file in `file_mappings`; in step mode the guide is not readable and never among the session-start reads
- No state persists across runs
- Write-occurred flag is monotonic (once `True`, never `False`)
- All policy checks occur before any filesystem mutation
- `verify` callback has no filesystem side effects
- Errors leave the filesystem unchanged
- A result with `supersedes` set supersedes the earlier non-stubbed result for the same file or tool command; a result with `supersedes` unset supersedes nothing
- A result supersedes at most one earlier result (at most one non-stubbed result exists per file or per the advance feedback at any time)
- A write or edit supersedes the file's earlier read result; the injected read provides the file's current content in the conversation
- An edit's replacement applies atomically (all or nothing): a replacement is never partially applied
- `replace_lines` requires the line-numbered view
- Termination tools never produce `ToolResult` and never supersede an earlier result
- Search results never render matches from writable files
- A tool result never carries the stub text
