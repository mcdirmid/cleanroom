<!-- Dependencies (md files to read alongside this one):
  - conversation_history.md
  - agent_loop.md
-->

# Interface LLS: runner_logger

## Data Types
```python
from typing import Any, Callable, Dict, Optional, Protocol, Tuple, TypeAlias
from conversation_history import LogEvent, LoggerCallback

class RunnerLogger(Protocol):
    def resolve_log_path(self) -> str: ...
    def format_compact_log(self, event: LogEvent, data: Dict[str, Any]) -> Optional[str]: ...
    def format_full_log(self, event: LogEvent, data: Dict[str, Any]) -> str: ...
    def create_agent_logger(self, log_path: str) -> Tuple[LoggerCallback, Callable[[], None]]: ...
```

## Term definitions

- **transcript logging** → term definition: the recording and formatting of agent loop execution events during a build pass
- **runner usage** → term definition: the accumulated token counts, request counts, and execution duration across all agent sessions in a runner pass
- **compact log** → term definition: single-line formatted event summaries suitable for standard output
- **verbose transcript** → term definition: detailed event summaries written to an unbuffered log file
- **run** → term definition from agent_loop
- **cumulative usage** → term definition from agent_loop

## Component-Provided Operations

### `resolve_log_path`

```python
def resolve_log_path(self) -> str
```

**Purpose:** Resolve the agent transcript log file path from environment variables and fallback paths.

**Preconditions:** None.

**Postconditions:**
- Returns the absolute or workspace-relative log file path.

**Failure Handling:** Always returns a valid string path.

**HLS Justification:** "Resolve the destination log file path from environment variables or default conventions."

### `format_compact_log`

```python
def format_compact_log(self, event: LogEvent, data: Dict[str, Any]) -> Optional[str]
```

**Purpose:** Format a one-line summary of an agent event for standard output.

**Preconditions:** None.

**Postconditions:**
- Returns formatted string for stdout-worthy events (`tool_called`, `run_terminated`, `error`), or `None` to skip output (e.g. `api_response`).

**Failure Handling:** Missing fields in `data` fallback to placeholder values.

**HLS Justification:** "Format a compact log line for standard output."

### `format_full_log`

```python
def format_full_log(self, event: LogEvent, data: Dict[str, Any]) -> str
```

**Purpose:** Format a verbose line representing an agent event for file logging.

**Preconditions:** None.

**Postconditions:**
- Returns a single formatted line containing event details and node attribution.

**Failure Handling:** Fallback formatting for unexpected events.

**HLS Justification:** "Format a verbose transcript line for file logging."

### `create_agent_logger`

```python
def create_agent_logger(self, log_path: str) -> Tuple[LoggerCallback, Callable[[], None]]
```

**Purpose:** Initialize an unbuffered file logger and cumulative usage tracker for a runner execution pass.

**Preconditions:**
- `log_path` is writable.

**Postconditions:**
- Returns `(logger_callback, closer_callback)` where `logger_callback` records events to stdout and disk, and `closer_callback` flushes and closes the log file.

**Failure Handling:** File creation failures propagate.

**HLS Justification:** "Create an agent logger callback and log-file closer for a runner pass."

## Invariants

- Log writes are flushed immediately to disk.
- Interrupted runs ensure log file closing.

## Non-Concerns

- Multi-process lock coordination.
