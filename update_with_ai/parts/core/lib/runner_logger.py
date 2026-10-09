# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T23:58:18Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: ec835b5c2999
# --- END CLEANROOM METADATA ---

# Requirements specified in runner_logger.pyi
from typing import NewType, Protocol
from dataclasses import dataclass

EventName = NewType("EventName", str)
EventSummary = NewType("EventSummary", str)
EventTranscript = NewType("EventTranscript", str)


@dataclass(frozen=True)
class RunnerLogEvent:
    event_name: EventName
    summary: EventSummary
    transcript: EventTranscript


class RunnerLogger(Protocol):
    def consume(self, event: RunnerLogEvent) -> None: ...
