from dataclasses import dataclass
from framework import data_type, operation, singleton_type

@data_type
@dataclass(frozen=True)
class LogEvent:
    """
PURPOSE:
Represents a captured execution action, exposing an event name, a source, and a summary.

FRESH_REQUIREMENTS:
- A log event record represents a captured execution action, exposing an event name, a source, and a summary.
"""

    def __init__(self, event_name: str, source: str, summary: str) -> None:
        ...

    @property
    def event_name(self) -> str:
        """
PURPOSE:
Exposes the name of the execution event.
"""
        ...

    @property
    def source(self) -> str:
        """
PURPOSE:
Exposes the component or subagent source of the event.
"""
        ...

    @property
    def summary(self) -> str:
        """
PURPOSE:
Exposes descriptive summary details of the execution event.
"""
        ...

@singleton_type('system')
class AntigravityRunLogger:
    """
PURPOSE:
System service that records execution activity and maintains transcript associations.
"""

    @operation
    def log_event(self, event_name: str, source: str, summary: str) -> None:
        """
PURPOSE:
Records an event name, a source, and a summary for an execution action.

FRESH_REQUIREMENTS:
- The antigravity run logger records an event name, a source, and a summary for an execution action.
"""
        ...

    @operation
    def register_transcript(self, identifier: str, slug: str) -> None:
        """
PURPOSE:
Associates a conversation identifier with a role slug.

FRESH_REQUIREMENTS:
- The antigravity run logger associates a conversation identifier with a role slug.
"""
        ...

    @operation
    def sanitize_slug(self, label: str) -> str:
        """
PURPOSE:
Converts a role label into a safe identifier string.

FRESH_REQUIREMENTS:
- The antigravity run logger converts a role label into a safe identifier string.
"""
        ...
