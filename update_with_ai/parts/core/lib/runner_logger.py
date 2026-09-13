from typing import Protocol
from dataclasses import dataclass

@dataclass(frozen=True)
class LogEvent:
    event_name: str
    summary: str
    transcript_representation: str

class RunnerLogger(Protocol):
    def consume(self, event: LogEvent) -> None:
        ...

