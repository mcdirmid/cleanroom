<!-- Dependencies (md files to read alongside this one):
  - tool_provider-low.md
  - dag_storage-low.md
  - dag_clean_logic-low.md
  - agent_loop-low.md
-->

# Interface LLS: sandbox

## Data Types
```python
from typing import Any, Literal, Protocol, TypeAlias
from dataclasses import dataclass

from tool_provider import ExecutionSignal, SupersessionFlag, ToolCall, ToolDefinition, ToolFailure, ToolResult, TerminationResult

VirtualName: TypeAlias = str
BlameTarget: TypeAlias = str
FileContent: TypeAlias = str
ChangeSummary: TypeAlias = str
GuideSummary: TypeAlias = str
StepSection: TypeAlias = str
SessionStartRead: TypeAlias = tuple[VirtualName, FileContent]

class Sandbox(Protocol):
    def get_tool_definitions(self) -> list[ToolDefinition]: ...
    def execute_tool_call(self, tool_call: ToolCall) -> tuple[list[ToolResult] | None, ExecutionSignal, TerminationResult | ToolFailure | None]: ...
    def has_modified_filesystem(self) -> bool: ...
    def get_session_start_reads(self) -> list[SessionStartRead]: ...
```

**VirtualName:** The name the agent uses to refer to a file; the sandbox resolves it to a full filesystem path.

**BlameTarget:** A dependency the agent may blame for task incompleteness.

**FileContent:** The complete content of a file.

**ChangeSummary:** A summary describing what changed in each file when files were modified.

**GuideSummary:** The guide's first part — content from the guide's first line through the end of its `## Summary` section.

**StepSection:** A checklist section of the guide, delimited by `## <name>` headings, delivered after an advance that passed verification.

**ToolCall:** A tool invocation consisting of a tool name and tool arguments.

## Term definitions

- **virtual name** → the `VirtualName` alias
- **file write** → term definition: any successful operation that modifies the filesystem
- **line-numbered view** → term definition: a rendering of a file's content with each line prefixed by its 1-indexed line number; the line numbers are metadata, never file content
- **injected read** → term definition: the read provided for a file immediately after a successful file write of that file, presenting a read request with line numbers and the read result carrying the file's full current content; the agent did not request it, and to the agent it appears as a numbered read it requested
- **session-start read** → term definition: a read of a file the agent can read but not write, provided at the beginning of a run for rendering before the agent's first turn; it renders the file's content plain, never supersedes an earlier result, and is never stubbed
- **template** → term definition: a writable file's initial content, configured for the file; when the file does not exist when the sandbox is configured, the file is created with the template's content at run start; a file that exists when the sandbox is configured is never modified by its template
- **guide** → term definition: the run's declared guide input — a readable file the node declares separately from its dependencies, at most one per run, in the guide format: its first line is `# Guide: <title>` and its first `##` heading is `## Summary`
- **change summary** → the `ChangeSummary` alias
- **guide summary** → the `GuideSummary` alias
- **step section** → the `StepSection` alias
- **step mode** → term definition: a run configuration in which the guide is not readable and its content reaches the agent only through the advance operation: the guide summary at run start, then the step sections one at a time after successful advances
- **blame** → term definition: a termination outcome that attributes the task's incompleteness to one or more dependencies and provides feedback on how to correct their outputs; blame is not failure
- **blame target** → the `BlameTarget` alias
- **soft length bound** → term definition: the preferred maximum length of a change summary; a summary exceeding it is rejected with shortening guidance up to a grace count, then accepted when within the hard length bound
- **hard length bound** → term definition: the maximum length a change summary may reach; a summary exceeding it is rejected with hard-bound guidance up to a grace count, and a summary still exceeding it after the grace count fails the run (success turns into failure)
- **run** → the `run` term from agent_loop
- **tool definition** → the `ToolDefinition` alias from tool_provider
- **tool result** → the `ToolResult` alias from tool_provider
- **supersession flag** → the `SupersessionFlag` alias from tool_provider
- **stub** → the `stub` term from tool_provider
- **termination result** → the `TerminationResult` alias from tool_provider
- **tool failure** → the `ToolFailure` alias from tool_provider
- **dependency** → the `dependency` term from dag_storage
- **change message** → the `change message` term from dag_clean_logic
- **feedback message** → the `feedback message` term from dag_clean_logic

## Component-Provided Operations

### `get_tool_definitions`

```python
def get_tool_definitions(self) -> list[ToolDefinition]: ...
```

**Purpose:** Request the list of available tool definitions for the sandbox tools (read_file, write_file, edit_file, replace_lines, search_files, advance, failure, blame).

**Preconditions:** None.

**Postconditions:** Returns the full list of available `ToolDefinition` objects conforming to the tool_provider schema.

**Failure Handling:** No failures expected; an empty list is returned if no tools are configured.

**HLS Justification:** Contract → Operations → "Request tool definitions (per tool_provider)."

### `execute_tool_call`

```python
def execute_tool_call(self, tool_call: ToolCall) -> tuple[list[ToolResult] | None, ExecutionSignal, TerminationResult | ToolFailure | None]: ...
```

**Purpose:** Execute a sandbox tool call by name with the provided arguments. Supports the following tools:
- **read_file:** Reads a file's entire content. Reads of non-writable files provide plain content; reads of writable files provide line numbers. A plain read of an existing writable file is rejected with a tool failure.
- **write_file:** Writes content to a file, creating it if it does not exist. After a successful write, an injected read provides the file's current content with line numbers.
- **edit_file:** Performs content-based search-and-replace of short text (bounded in length); replaces exactly one occurrence by default, or all occurrences when expect_multiple=True. Replacement applies atomically (all or nothing).
- **replace_lines:** Replaces, deletes, or inserts lines by 1-indexed line range. Requires a line-numbered view (must follow a read with line numbers).
- **search_files:** Recursively searches for a regex pattern within files within a specified path. Renders matches only for files that are not writable; matches in writable files are reported as counts without content. Results beyond the search result limit signal a tool failure advising offset/limit pagination.
- **advance:** Signals successful termination when verification passes. When files were modified, requires a change summary naming what changed in each file. A summary exceeding the soft length bound is rejected with shortening guidance; a summary exceeding the hard length bound is rejected with hard-bound guidance. Persistent rejection of change summaries fails the run. In step mode, an advance with step sections remaining carries no change summary.
- **failure:** Ends the session in failure.
- **blame:** Attributes the task's incompleteness to one or more blame targets and provides feedback; each (target, feedback) pair is delivered as a feedback message to the blamed node.

**Preconditions:** The sandbox is configured and initialized. For writable file operations, the file path must be within the configured writable paths. For blame, blame targets must be configured.

**Postconditions:** Returns a tuple of (tool results or None, execution signal, termination result or tool failure). The execution signal indicates whether the session continues or terminates. When a file write occurs, an `injected read` follows automatically. File read operations return `ToolResult` with file content. File write operations create or overwrite files. Search operations return matches for non-writable files or counts for writable files. The `advance` tool may return a `ToolFailure` if the change summary is missing, malformed, or incomplete when files were modified. The `failure` tool returns a termination signal indicating failure. The `blame` tool returns a termination signal attributing the task to blame targets.

**Failure Handling:**
- Policy violation (e.g., reading/writing outside configured paths): returns a `ToolFailure` identifying the violated policy.
- Plain read of existing writable file: returns a `ToolFailure` requiring a read with line numbers.
- replace_lines without prior line-numbered read: returns a `ToolFailure`.
- Search results exceeding limit: returns a `ToolFailure` advising offset/limit pagination.
- Missing/malformed change summary when files were modified: returns a `ToolFailure`.
- Change summary exceeding hard length bound after grace count: returns a failure termination signal.
- Blame invoked without configured blame targets: returns a `ToolFailure`.
- Blame target not in configured blame targets: returns a `ToolFailure`.
- All errors leave the filesystem unchanged and identify the violated policy or failing operation.

**HLS Justification:** Contract → Operations → "Execute a tool call"; Contract → Guarantees → all guarantee statements; File operations, Views, Stubbing, Auto re-read, Session-start reads, Step mode, Template initialization, Verification, Termination sections.

### `has_modified_filesystem`

```python
def has_modified_filesystem(self) -> bool: ...
```

**Purpose:** Query whether the run has modified the filesystem.

**Preconditions:** The sandbox is configured and initialized.

**Postconditions:** Returns `True` if any file write has occurred during the run (excluding template initialization, which is not a run write). Returns `False` otherwise.

**Failure Handling:** None expected.

**HLS Justification:** Contract → Operations → "Query whether the run has modified the filesystem." Guarantees → "Signals whether any file write has occurred during the run."

### `get_session_start_reads`

```python
def get_session_start_reads(self) -> list[SessionStartRead]: ...
```

**Purpose:** Request the session-start reads for all files that are readable but not writable.

**Preconditions:** The sandbox is configured and initialized. Session-start reads must be enabled in configuration.

**Postconditions:** Returns a list of (virtual name, file content) pairs for every file that is readable but not writable, in deterministic order sorted by virtual name. Each read renders the file's content plain and never supersedes an earlier result.

**Failure Handling:** Returns an empty list if session-start reads are disabled or no readable-but-not-writable files are configured.

**HLS Justification:** Contract → Operations → "Request the session-start reads." Session-start reads section.

## Invariants

- Permissions are enforced for all operations: the sandbox never allows reading or writing outside configured paths.
- A read provides the file's entire content; reads are not paginated and are not bounded by a size limit.
- An edit's replacement applies atomically (all or nothing).
- Error messages identify the violated policy or the failing operation; errors leave the filesystem unchanged.
- Template initialization is not a run write: it never signals that the run modified the filesystem and is never a changed file.
- Session-start reads are never stubbed and never supersede an earlier result.
- In step mode, the guide is not readable: its content reaches the agent only through the advance operation's outputs.
- A failing verification prevents progressing to the next step section; advance never terminates on a failing verification.
- Termination is at the agent's judgment: the agent signals termination when it considers its task complete, or when it cannot be completed.
- Advance signals successful termination when verification passes; blame signals successful termination with attribution; failure ends the session in failure.

## Non-Concerns

- **Error message wording:** error messages identify the violated policy or failing operation; their exact wording is unspecified — the HLS states this as a non-concern.
- **Session-start read size:** session-start reads inherit the unbounded-read rule; the read-only files are assumed to be reasonably sized, so no separate size bound is introduced for session-start reads — the HLS states this as a non-concern.
- **Template size:** templates are assumed to be reasonably sized, so no separate size bound is introduced for template content — the HLS states this as a non-concern.
- **Step section size:** step sections are parts of the guide file, which is assumed reasonably sized; no separate size bound is introduced for step sections — the HLS states this as a non-concern.
- **Guide parsing:** the exact rules for splitting the guide into its guide summary and step sections follow the guide format; section content is delivered in order without interpretation — the HLS states this as a non-concern.
- **Step presentation:** the exact wording of the ensure instruction and the formatting of the summary and step sections within an advance output are unspecified; the intent is conveyed by the Step mode rules — the HLS states this as a non-concern.
- **Advance tool description:** the advance tool's description wording is unspecified; the tool's contract is defined by the Verification, Termination, and Step mode rules — the HLS states this as a non-concern.
- **Stub text:** the exact text of a stub placeholder is unspecified; the stub placeholder is an implementation detail that does not affect observable behavior — the HLS states this as a non-concern.
- **Tool argument validation details:** the specific validation rules for each tool's arguments are implementation details, bounded by the tool_provider contract — the HLS states this as an assumption.
- **File system implementation:** the underlying filesystem implementation is unspecified; the sandbox operates on file paths resolved from virtual names — the HLS states this as a non-concern.
