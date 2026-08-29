<!-- Dependencies (md files to read alongside this one):
  - runner_logger.md
  - conversation_history.md
  - agent_loop.md
-->

# Implementation LLS: runner_logger_impl

## Data Types
```python
from runner_logger import RunnerLogger

class RunnerLoggerImpl(RunnerLogger):
    def __init__(self) -> None: ...
```

## Behavioral Description
Implements RunnerLogger with compact stdout event formatting, unbuffered log file output, and cumulative usage aggregation.

## Invariants
- `api_response` events are suppressed in compact stdout formatting.
- `run_terminated` updates runner cumulative usage across all sessions.
