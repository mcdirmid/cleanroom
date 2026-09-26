from dataclasses import dataclass
from typing import Protocol
from framework import data_type, operation, singleton_type


@dataclass(frozen=True)
@data_type
class RunnerLogEvent:
    """Record of an observable execution event.

    Args:
        event_name: Name of the logged event.
        summary: Compact single-line summary of the event.
        transcript_representation: Verbose detailed representation for transcript logs.
    """
    event_name: str
    summary: str
    transcript_representation: str


@singleton_type("system")
class RunnerLogger(Protocol):
    """Defined as a system service that formats and records log events."""

    @operation
    def consume(self, event: RunnerLogEvent) -> None:
        """Consumes a runner log event, writing summary to stdout and full record to transcript log.

        Args:
            event: The log event to record.

        REQUIREMENTS:
        - The runner logger consumes runner log events, writing compact single-line summaries to standard output and full verbose records to a transcript log file.

        GROUNDING_PROVISIONS:
        - action("consume_log_event", RunnerLogEvent): Records log event to stdout and transcript log to satisfy requirement 2.
        """
        ...
