<!-- Dependencies (md files to read alongside this one):
-->

# Interface LLS: runner_logger

## Data Types
```python
from typing import Protocol, TypeAlias
from dataclasses import dataclass

EventName: TypeAlias = str
EventSummary: TypeAlias = str
TranscriptEntry: TypeAlias = str

@dataclass(frozen=True)
class LogEvent:
    name: EventName
    summary: EventSummary
    transcript: TranscriptEntry

class RunnerLogger(Protocol):
    def log(self, event: LogEvent) -> None: ...
```

- `EventName` → corresponds to event name: a brief identifier for an execution event.
- `EventSummary` → corresponds to single-line summary: a concise, single-line representation suitable for standard output.
- `TranscriptEntry` → corresponds to verbose transcript representation: a detailed formatted entry for unbuffered disk logging.
- `LogEvent` → corresponds to *log event*: a structured record of an observable execution event.
- `RunnerLogger` → corresponds to *runner logger*: a service that formats and records *log events*.

## Term definitions

- **log event** → the `LogEvent` alias
- **runner logger** → term definition: a service that formats and records *log events*

## Component-Provided Operations

### `log`

```python
def log(self, event: LogEvent) -> None: ...
```

**Purpose:** (RunnerLogger) Consumes an observable execution event, writing a compact summary to standard output and full records to the transcript log.

**Preconditions:** None.

**Postconditions:**
- Writes the event's single-line summary to standard output.
- Writes the event's verbose transcript representation to the unbuffered transcript log.

**Failure Handling:** Logging failures do not abort execution; unexpected filesystem errors are handled gracefully without corrupting run state.

**HLS Justification:** "A *runner logger* consumes *log events*, writing summaries to standard output and full records to a transcript log."

## Invariants

- Log event writes to disk are unbuffered and flushed immediately.
- A `LogEvent` provides both a single-line summary for stdout and a verbose transcript representation for disk recording.
