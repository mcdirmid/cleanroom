# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T20:52:01Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 8a5b833a18f0
# --- END CLEANROOM METADATA ---

"""Runner logger low-level interface specification."""

from dataclasses import dataclass
from typing import NewType, Protocol
from framework import data_type, operation, singleton_type
from support.lib.lifecycle import InTier, SystemTier

EventName = NewType("EventName", str)
EventSummary = NewType("EventSummary", str)
EventTranscript = NewType("EventTranscript", str)


@dataclass(frozen=True)
@data_type
class RunnerLogEvent:
    """Record of an observable execution event.

    Args:
        event_name: Unique identifier or category name of the event.
        summary: Single-line compact summary string for live visibility.
        transcript: Detailed verbose text representation for audit logging.
    """
    event_name: EventName
    summary: EventSummary
    transcript: EventTranscript


@singleton_type("system")
class RunnerLogger(InTier[SystemTier], Protocol):
    """System service consuming execution log events."""

    @operation
    def consume(self, event: RunnerLogEvent) -> None:
        """Consumes a runner log event, writing to standard output and transcript file.

        Args:
            event: The execution event record to consume.

        PRECONDITIONS:
        - A caller supplies a runner log event.

        POSTCONDITIONS:
        - MUST write a single-line summary to standard output.
        - MUST write the verbose transcript representation to the transcript log file.
        """
        ...
