<!-- Dependencies (md files to read alongside this one):
  - tool_provider.md
  - loop_guard.md
-->

# Implementation LLS: loop_guard_impl

## Data Types
```python
from typing import Optional
from loop_guard import LoopGuard, LoopGuardConfig

class LoopGuardImpl(LoopGuard):
    def __init__(self, config: Optional[LoopGuardConfig] = None) -> None: ...
```

## Behavioral Description

- `LoopGuardImpl` tracks consecutive executions of identical tools with identical arguments using default thresholds (reminder threshold = 3, fatal threshold = 6) when not overridden by `config`.
- Produces a `LoopReminder` when consecutive identical tool executions reach the reminder threshold.
- Produces a `LoopFailure` communicating session failure when consecutive identical tool executions reach the fatal threshold.
- Tracks consecutive edits to the same file and line range, producing a `LoopReminder` at the reminder threshold and a `LoopFailure` at the fatal threshold.
- Resets internal repetition counters when a tool execution demonstrates forward progress.

## Invariants

- Counter increments require identical tool arguments or exact matching file paths and line bounds.
- Forward progress resets all repetition counters to zero.
- Reaching fatal threshold produces a terminal failure signal.
