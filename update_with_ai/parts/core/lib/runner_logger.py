# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
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
    # TODO_RunnerLogEvent_body
    event_name: EventName
    summary: EventSummary
    transcript: EventTranscript


class RunnerLogger(Protocol):
    def consume(self, event: RunnerLogEvent) -> None:
        # TODO_consume_body
        ...
