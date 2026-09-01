<!-- Dependencies (md files to read alongside this one):
  - tool_provider.md
-->

# Interface LLS: loop_guard

## Data Types
```python
from typing import Protocol, TypeAlias, Optional, Union
from dataclasses import dataclass
from tool_provider import ToolArguments, ToolResult, ToolFailure, ToolName

ReminderThreshold: TypeAlias = int
FatalThreshold: TypeAlias = int
FilePath: TypeAlias = str
LineRange: TypeAlias = tuple[int, int]

@dataclass(frozen=True)
class LoopGuardConfig:
    reminder_threshold: ReminderThreshold
    fatal_threshold: FatalThreshold

LoopReminder: TypeAlias = ToolResult
LoopFailure: TypeAlias = ToolFailure

class LoopGuard(Protocol):
    def record_tool_call(self, tool_name: ToolName, arguments: ToolArguments) -> Optional[Union[LoopReminder, LoopFailure]]: ...
    def record_file_edit(self, file_path: FilePath, line_range: LineRange) -> Optional[Union[LoopReminder, LoopFailure]]: ...
    def reset_progress(self) -> None: ...
```

- `ReminderThreshold` → corresponds to warning threshold for repetition.
- `FatalThreshold` → corresponds to fatal threshold for repetition.
- `FilePath` → corresponds to workspace file path.
- `LineRange` → corresponds to line range tuple.
- `LoopGuardConfig` → corresponds to loop guard configuration.
- `LoopReminder` → corresponds to *loop reminder*: feedback warning an agent of detected repetition.
- `LoopFailure` → corresponds to *loop failure*: an outcome signaling that an agent run has failed due to unresolvable repetition.
- `LoopGuard` → corresponds to *loop guard*: a monitor that tracks repetitive execution patterns during an agent run.

## Term definitions

- **loop guard** → term definition: a monitor that tracks repetitive execution patterns during an agent run
- **loop reminder** → the `LoopReminder` alias
- **loop failure** → the `LoopFailure` alias

## Component-Provided Operations

### `record_tool_call`

```python
def record_tool_call(self, tool_name: ToolName, arguments: ToolArguments) -> Optional[Union[LoopReminder, LoopFailure]]: ...
```

**Purpose:** (LoopGuard) Records a tool execution and checks for identical consecutive calls.

**Preconditions:** None.

**Postconditions:**
- Returns a `LoopReminder` if consecutive identical calls reach `reminder_threshold`.
- Returns a `LoopFailure` if consecutive identical calls reach `fatal_threshold`.
- Returns `None` if repetition is within acceptable bounds.

**Failure Handling:** Exceeding fatal threshold produces a terminal `LoopFailure`.

**HLS Justification:** "Consecutive repetitions reaching a warning threshold produce a *loop reminder*."

### `record_file_edit`

```python
def record_file_edit(self, file_path: FilePath, line_range: LineRange) -> Optional[Union[LoopReminder, LoopFailure]]: ...
```

**Purpose:** (LoopGuard) Records a file edit and checks for oscillating consecutive edits.

**Preconditions:** None.

**Postconditions:**
- Returns a `LoopReminder` if consecutive identical edits reach `reminder_threshold`.
- Returns a `LoopFailure` if consecutive identical edits reach `fatal_threshold`.
- Returns `None` if repetition is within acceptable bounds.

**Failure Handling:** Exceeding fatal threshold produces a terminal `LoopFailure`.

**HLS Justification:** "A *loop guard* evaluates consecutive executions of identical *tools* and edits."

### `reset_progress`

```python
def reset_progress(self) -> None: ...
```

**Purpose:** (LoopGuard) Resets repetition counters upon observable forward progress.

**Preconditions:** None.

**Postconditions:**
- Clears repetition counters back to zero.

**Failure Handling:** Always succeeds.

**HLS Justification:** "Executing a tool that demonstrates progress clears repetition tracking in a *loop guard*."

## Invariants

- Repetition counters increment only for strictly identical consecutive operations.
- Forward progress resets all repetition counters.
