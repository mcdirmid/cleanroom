from __future__ import annotations
from support.lib.lifecycle import Singleton, SystemTier
from typing import NewType, Protocol
from dataclasses import dataclass

# Requirements specified in logger.pyi

EventName = NewType('EventName', str)

EventSummary = NewType('EventSummary', str)

EventTranscript = NewType('EventTranscript', str)

@dataclass(frozen=True)
class RunnerLogEvent:
    # Contract: encapsulates observable execution event fields (event_name, summary, transcript)
    event_name: EventName
    summary: EventSummary
    transcript: EventTranscript


class RunnerLogger(Singleton[SystemTier], Protocol):
    # Contract: consume execution log event, writing single-line summary to stdout and verbose transcript to file
    def consume(self, event: RunnerLogEvent) -> None:
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-09T02:18:06Z
# CHANGE: Align with logger.pyi specification
# --- END CLEANROOM METADATA ---
