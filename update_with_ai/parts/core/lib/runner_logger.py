# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-09T02:18:06Z
# CHANGE: Align with runner_logger.pyi specification
# CODE_HASH: 8e8c85722687
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from typing import NewType, Protocol
from dataclasses import dataclass

# Requirements specified in runner_logger.pyi

EventName = NewType('EventName', str)

EventSummary = NewType('EventSummary', str)

EventTranscript = NewType('EventTranscript', str)

@dataclass(frozen=True)
class RunnerLogEvent:
    # Contract: encapsulates observable execution event fields (event_name, summary, transcript)
    event_name: EventName
    summary: EventSummary
    transcript: EventTranscript


class RunnerLogger(Protocol):
    # Contract: consume execution log event, writing single-line summary to stdout and verbose transcript to file
    def consume(self, event: RunnerLogEvent) -> None:
        ...
