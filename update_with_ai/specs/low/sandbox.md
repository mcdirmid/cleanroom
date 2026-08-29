<!-- Dependencies (md files to read alongside this one):
  - tool_provider.md
  - dag_storage.md
  - dag_clean_logic.md
  - file_view.md
  - guide_delivery.md
  - run_control.md
-->

# Interface LLS: sandbox

## Data Types
```python
from dataclasses import dataclass, field
from typing import Protocol, TypeAlias
from tool_provider import PresentedToolResult, ToolCallOutcome, ToolDefinition
from file_view import (
    FileMapping,
    ReadablePaths,
    SearchResultLimit,
    TemplateMapping,
    VirtualName,
    WritablePaths,
    WriteOccurred,
)
from run_control import Blame, BlameTargets, VerificationCallback

@dataclass
class SandboxConfig:
    file_mappings: FileMapping
    readable_paths: ReadablePaths
    writable_paths: WritablePaths
    blame_targets: BlameTargets
    search_result_limit: SearchResultLimit
    session_start_reads_enabled: bool = True
    guide: VirtualName | None = None
    step_sections_enabled: bool = True
    feedback_pending: bool = False
    templates: TemplateMapping = field(default_factory=dict)
    verification_callback: VerificationCallback = None

class Sandbox(Protocol):
    def get_tool_definitions(self) -> list[ToolDefinition]: ...
    def get_session_start_reads(self) -> list[PresentedToolResult]: ...
    def read_file(self, file_path: VirtualName, include_line_numbers: bool = False) -> ToolCallOutcome: ...
    def replace(self, file_path: VirtualName, old_str: str, new_str: str, expect_multiple: bool = False) -> ToolCallOutcome: ...
    def update_lines(self, file_path: VirtualName, start_line: int, end_line: int, new_str: str) -> ToolCallOutcome: ...
    def search_files(self, path: VirtualName = ".", pattern: str = "", offset: int | None = None, limit: int | None = None) -> ToolCallOutcome: ...
    def advance(self, changes: list[dict[str, str]] = []) -> ToolCallOutcome: ...
    def fail(self) -> ToolCallOutcome: ...
    def blame(self, blames: list[Blame]) -> ToolCallOutcome: ...
    def get_write_occurred(self) -> WriteOccurred: ...
```

`SandboxConfig` is the aggregate client-supplied configuration for the sandbox: file mappings (each file's virtual name to its full path), the readable and writable virtual names, the blame targets (a mapping from each blameable artifact's virtual name to the node that owns it), the search result limit, whether session-start reads are enabled (default: enabled), the guide (default: none — the declared guide's virtual name, a file in `file_mappings`), whether step mode is enabled (default: enabled), whether feedback is pending (default: false), the templates (default: empty), and an optional verification callback.

The sandbox is a facade: it composes the file machinery (`file_view`), the step-mode guide delivery (`guide_delivery`), and the verification and termination rules (`run_control`) into a single tool surface. Each operation below delegates to the owning component's operation; the composition itself is described in the implementation spec.
## Term definitions

- **virtual name** → the `VirtualName` alias from file_view
- **file write** → term definition from file_view
- **line-numbered view** → term definition from file_view
- **injected read** → term definition from file_view
- **session-start read** → term definition from file_view
- **template** → term definition from file_view
- **guide** → term definition from guide_delivery
- **guide summary** → term definition from guide_delivery
- **step section** → term definition from guide_delivery
- **step mode** → term definition from guide_delivery
- **blame** → term definition from run_control
- **blame target** → the `BlameTarget` alias from run_control
- **soft length bound** → term definition from run_control
- **hard length bound** → term definition from run_control
- **tool definition** → the `ToolDefinition` alias from tool_provider
- **tool result** → the `ToolResult` type from tool_provider
- **supersession flag** → term definition from tool_provider
- **stub** → term definition from tool_provider
- **termination result** → the `TerminateSuccessResult` type from tool_provider
- **tool failure** → the `ToolFailure` type from tool_provider
- **dependency** → the `NodeDependencies` alias from dag_storage
- **change message** → term definition from dag_clean_logic
- **feedback message** → term definition from dag_clean_logic

## Component-Provided Operations

### `get_tool_definitions`

```python
def get_tool_definitions(self) -> list[ToolDefinition]
```

**Purpose:** Return the composed tool registry: the file tools, the advance tool, and the termination tools, presented together as the sandbox's tool surface.

**Preconditions:** The sandbox has been configured with the aggregate `SandboxConfig`.

**Postconditions:** Delegates to the components' tool definitions and composes them into one list (per the composition described in the implementation spec): the file tools from `file_view.get_tool_definitions`, the advance tool from `guide_delivery.get_tool_definitions` (its parameters per the step state), and the termination tools from `run_control.get_tool_definitions` — the failure tool always, the blame tool only when blame targets are configured. Each definition follows the JSON schema format expected by the model (as defined in `tool_provider`).

**Failure Handling:** No failure conditions.

**HLS Justification:** "Request tool definitions (per tool_provider)."


### `get_session_start_reads`

```python
def get_session_start_reads(self) -> list[PresentedToolResult]
```

**Purpose:** Return the session-start reads for rendering at the beginning of a session before the model's first turn: the plain reads of the read-only files and, in step mode, the guide's presentation.

**Preconditions:** None.

**Postconditions:** Delegates to `file_view.get_session_start_reads` (the plain reads of the read-only files) and `guide_delivery.get_session_start_reads` (the guide's presentation at session start — in step mode, the pre-injected advance call); the results are presented together before the model's first turn; requesting them changes no sandbox state.

**Failure Handling:** Always succeeds; filesystem errors reading a readable file are unhandled.

**HLS Justification:** "Request the session-start reads."


### `read_file`

```python
def read_file(self, file_path: VirtualName, include_line_numbers: bool = False) -> ToolCallOutcome
```

**Purpose:** Read a file's entire content using the virtual name provided by the agent.

**Preconditions:** Per `file_view.read_file` (the file machinery's rules apply).

**Postconditions:** Delegates to `file_view.read_file`; the file_view rules apply (per the file_view LLS).

**Failure Handling:** Per `file_view.read_file`'s failure signals, returned as-is.

**HLS Justification:** "Execute a tool call."


### `replace`

```python
def replace(self, file_path: VirtualName, old_str: str, new_str: str,
            expect_multiple: bool = False) -> ToolCallOutcome
```

**Purpose:** Replace text in a file by content-based search and replace.

**Preconditions:** Per `file_view.replace` (the file machinery's rules apply).

**Postconditions:** Delegates to `file_view.replace`; the file_view rules apply (per the file_view LLS).

**Failure Handling:** Per `file_view.replace`'s failure signals, returned as-is.

**HLS Justification:** "Execute a tool call."


### `update_lines`

```python
def update_lines(self, file_path: VirtualName, start_line: int, end_line: int,
                 new_str: str) -> ToolCallOutcome
```

**Purpose:** Replace, delete, or insert lines in a file by 1-indexed line range.

**Preconditions:** Per `file_view.update_lines` (the file machinery's rules apply).

**Postconditions:** Delegates to `file_view.update_lines`; the file_view rules apply (per the file_view LLS).

**Failure Handling:** Per `file_view.update_lines`'s failure signals, returned as-is.

**HLS Justification:** "Execute a tool call."


### `search_files`

```python
def search_files(self, path: VirtualName = ".", pattern: str = "",
                 offset: int | None = None,
                 limit: int | None = None) -> ToolCallOutcome
```

**Purpose:** Search for a pattern in files using the virtual path provided by the agent.

**Preconditions:** Per `file_view.search_files` (the file machinery's rules apply).

**Postconditions:** Delegates to `file_view.search_files`; the file_view rules apply (per the file_view LLS).

**Failure Handling:** Per `file_view.search_files`'s failure signals, returned as-is.

**HLS Justification:** "Execute a tool call."


### `advance`

```python
def advance(self, changes: list[dict[str, str]] = []) -> ToolCallOutcome
```

**Purpose:** Signal the session's completion: verification, step-mode delivery, and termination sequence within the advance. The agent calls this when it has nothing more to do or considers its task complete.

**Preconditions:** Per `run_control.advance`'s preconditions (the change-message requirement applies only to the terminating advance) and the step mode rules from guide_delivery.

**Postconditions:** Delegates to `run_control.advance`, which sequences verification, the step-mode output (per guide_delivery's output rule), and the termination machinery; the advance sequencing is described in the implementation spec.

**Failure Handling:** Per `run_control.advance`'s failure signals, returned as-is (including the change-message and feedback-pending `ToolFailure` signals; a failing verification never signals a tool failure).

**HLS Justification:** "Execute a tool call."


### `fail`

```python
def fail(self) -> ToolCallOutcome
```

**Purpose:** End the session in failure. The agent calls this when it considers the task cannot be completed.

**Preconditions:** No termination signal has been produced yet in the current session.

**Postconditions:** Delegates to `run_control.fail`.

**Failure Handling:** Per `run_control.fail`.

**HLS Justification:** "Execute a tool call."


### `blame`

```python
def blame(self, blames: list[Blame]) -> ToolCallOutcome
```

**Purpose:** Signal termination with blame: attribute the task's incompleteness to dependencies and provide feedback on how to correct their outputs.

**Preconditions:** Per `run_control.blame` (blame targets are configured; each pair's target must be a key of the `blame_targets` mapping).

**Postconditions:** Delegates to `run_control.blame`.

**Failure Handling:** Per `run_control.blame`'s failure signals, returned as-is.

**HLS Justification:** "Execute a tool call."


### `get_write_occurred`

```python
def get_write_occurred(self) -> WriteOccurred
```

**Purpose:** Return whether the agent has modified the filesystem during the current session.

**Preconditions:** None.

**Postconditions:** Delegates to `file_view.get_write_occurred`: returns `True` if any file write has succeeded during the current session; `False` otherwise.

**Failure Handling:** Always succeeds.

**HLS Justification:** "Query whether the session modified the filesystem."

## Invariants

- The session begins when the sandbox is configured and ends when the agent signals termination
- No state persists across runs
- The tool surface composes the components' operations: file_view provides the file tools, run_control provides the termination tools, and guide_delivery provides the step-mode delivery; the composed tools are presented together
- The blame tool is offered only when blame targets are configured
- In a single advance, verification precedes step delivery and termination
- A failing verification produces feedback and no step delivery, and never terminates the run
- A passing verification with step sections remaining delivers the next step section
- A passing verification with no step sections remaining proceeds to the termination machinery
- The change summary applies only when advance terminates: in step mode, an advance with step sections remaining carries no change summary
- The feedback obligation is not disclosed to the agent before advance is attempted without a change; it surfaces only through advance's rejection
- Errors leave the filesystem unchanged (per file_view and run_control)

## Non-Concerns

- **Error message wording:** error messages identify the violated policy or the failing operation; their exact wording is unspecified.
- **Component internals:** how the components implement their contracts is governed by the components' own specs; the facade adds only composition.
