"""Runner logger interface and log event definition."""

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
    def log(self, event: LogEvent) -> None:
        ...
