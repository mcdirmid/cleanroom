from framework import data_type, operation, singleton_type
from typing import Protocol
from dataclasses import dataclass

@dataclass(frozen=True)
@data_type
class LogEvent:
    """
PURPOSE:
Record of an observable execution event
"""

    def __init__(self, event_name: str, summary: str, transcript_representation: str) -> None:
        ...

    @property
    def event_name(self) -> str:
        """
PURPOSE:
Name of the logged event
"""
        ...

    @property
    def summary(self) -> str:
        """
PURPOSE:
Compact single-line summary of the event
"""
        ...

    @property
    def transcript_representation(self) -> str:
        """
PURPOSE:
Verbose detailed representation for transcript logs
"""
        ...

@singleton_type('system')
class RunnerLogger(Protocol):
    """
PURPOSE:
Defined as a system service that formats and records log events
"""

    @operation
    def consume(self, event: LogEvent) -> None:
        """
PURPOSE:
Consumes a log event, writing summary to stdout and full record to transcript log

FRESH_REQUIREMENTS:
- The runner logger consumes log events, writing compact single-line summaries to standard output and full verbose records to a transcript log file.
"""
        ...
