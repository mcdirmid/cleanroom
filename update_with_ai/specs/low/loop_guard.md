<!-- Dependencies (md files to read alongside this one):
  - tool_provider.md
-->

# Interface LLS: loop_guard

## Data Types
```python
from typing import Any, Protocol, TypeAlias
from tool_provider import ToolCall

LoopDecision: TypeAlias = tuple[bool, str | None, str | None]

class LoopGuard(Protocol):
    def reset(self) -> None: ...
    def record_tool_call(self, tool_call: ToolCall) -> LoopDecision: ...
    def check_degenerate_response(self, content: str | None) -> bool: ...
    def get_termination_reminder(self) -> str: ...
```

The loop decision tuple `(is_stop, reminder_message, error_message)` conveys the evaluation of a tool call: whether the loop must abort, an optional reminder to inject, or a fatal loop error description.

## Term definitions

- **loop repetition** → term definition: consecutive execution of identical tool calls with identical arguments
- **range repetition** → term definition: consecutive file-editing tool calls targeting the same file path and line numbers
- **loop reminder** → term definition: a warning message injected into the conversation advising the agent to make progress or terminate
- **degenerate loop** → term definition: a failure condition triggered when repetition reaches eight consecutive iterations
- **degenerate response** → term definition: a truncated response whose content is a single character repeated
- **tool call** → the `ToolCall` alias from tool_provider
- **session** → term definition from tool_provider

## Component-Provided Operations

### `reset`

```python
def reset(self) -> None
```

**Purpose:** Resets repetition tracking counters and reminder injection flags.

**Preconditions:** None

**Postconditions:**
- Repetition tracking counters reset to zero
- Reminder injected flag set to false

**Failure Handling:** None

**HLS Justification:** "No tracking state persists across runs."

### `record_tool_call`

```python
def record_tool_call(self, tool_call: ToolCall) -> LoopDecision
```

**Purpose:** Evaluates a tool call for loop repetition and range repetition.

**Preconditions:**
- `tool_call` contains tool name and arguments

**Postconditions:**
- If the tool is `advance`, resets repetition tracking and returns `(False, None, None)`
- If identical tool calls repeat 4 consecutive times and reminder not yet injected, returns `(False, reminder, None)`
- If identical tool calls repeat 8 consecutive times, returns `(True, None, error)`
- If `update_lines` edits the same file and line range 4 consecutive times and reminder not yet injected, returns `(False, reminder, None)`
- If `update_lines` edits the same file and line range 8 consecutive times, returns `(True, None, error)`
- Otherwise returns `(False, None, None)`

**Failure Handling:** None

**HLS Justification:** "Evaluate a tool call for loop repetition and range repetition."

### `check_degenerate_response`

```python
def check_degenerate_response(self, content: str | None) -> bool
```

**Purpose:** Checks whether a truncated model response consists of a single character repeated.

**Preconditions:** None

**Postconditions:**
- Returns true if `content` is a non-empty string and all characters in `content` are identical; otherwise returns false

**Failure Handling:** None

**HLS Justification:** "Evaluate whether a truncated model response is degenerate."

### `get_termination_reminder`

```python
def get_termination_reminder(self) -> str
```

**Purpose:** Provides the termination reminder text when a model stops without requesting tool execution.

**Preconditions:** None

**Postconditions:**
- Returns the configured generator's reminder message if configured, otherwise returns the default termination reminder text

**Failure Handling:** None

**HLS Justification:** "Provide a termination reminder when the model stops with content without requesting tool execution."

## Invariants

- At most one reminder injected per run across all detectors
- The advance tool is exempt from repetition tracking and resets tracking state
- Eight consecutive repetitions trigger degenerate loop failure
- No state persists across runs

## Non-Concerns

- **Reminder wording:** The exact phrasing of reminder messages is unspecified.
