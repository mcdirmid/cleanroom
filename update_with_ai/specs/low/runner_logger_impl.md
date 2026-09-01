<!-- Dependencies (md files to read alongside this one):
  - runner_logger.md
-->

# Implementation LLS: runner_logger_impl

## Data Types
```python
from typing import Optional, TypeAlias
from runner_logger import RunnerLogger

TranscriptPath: TypeAlias = str

class RunnerLoggerImpl(RunnerLogger):
    def __init__(self, transcript_file_path: Optional[TranscriptPath] = None) -> None: ...
```

## Behavioral Description

- `RunnerLoggerImpl` clears any existing transcript log file at initialization.
- `RunnerLoggerImpl` formats and prints single-line compact event summaries directly to standard output.
- `RunnerLoggerImpl` writes full event details to an unbuffered disk transcript file.
- The transcript destination defaults to agent_loop.log or is resolved from configured environment variables.
- Intercepts termination signals to flush unwritten logs to disk before process exit.

## Invariants

- Every logged event produces an immediate unbuffered disk write.
