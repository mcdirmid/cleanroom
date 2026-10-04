"""Runner logger grounding specification module."""

from __future__ import annotations
from dataclasses import dataclass
from typing import NewType, Protocol
from support.lib.grounding_support import InTier, SystemTier

EventName = NewType("EventName", str)
EventSummary = NewType("EventSummary", str)
EventTranscript = NewType("EventTranscript", str)


@dataclass(frozen=True)
class RunnerLogEvent:
    """Record of an observable execution event.

    COVERED:
    - Encapsulates event_name, summary, and transcript fields.
    """
    event_name: EventName
    summary: EventSummary
    transcript: EventTranscript


class RunnerLogger(InTier[SystemTier], Protocol):
    """System service consuming execution log events."""

    def consume(self, event: RunnerLogEvent) -> None:
        """
        COVERED:
        - Information accessibility: accesses event.event_name, event.summary, event.transcript.

        DEFERRED:
        - MUST write a single-line summary to standard output.
        - MUST write the verbose transcript representation to the transcript log file.        """
        _name: EventName = event.event_name
        _summary: EventSummary = event.summary
        _transcript: EventTranscript = event.transcript
        raise NotImplementedError

