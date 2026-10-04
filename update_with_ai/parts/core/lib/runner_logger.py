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
