from dataclasses import dataclass
from framework import data_type, operation, singleton_type

@data_type
@dataclass(frozen=True)
class AntigravityLogEvent:
    """Represents a captured execution action.

    REQUIREMENTS:
    - An antigravity log event record represents a captured execution action, exposing an event name, a source, and a summary.

    GROUNDING_PROVISIONS:
    - knows("event_name", Self)
    - knows("source", Self)
    - knows("summary", Self)
    """

    def __init__(self, event_name: str, source: str, summary: str) -> None:
        ...


    @property
    def summary(self) -> str:
        ...


@singleton_type('system')
class AntigravityRunLogger:
    """System service that records execution activity and maintains transcript associations.

    REQUIREMENTS:
    - The antigravity run logger records an event name, a source, and a summary for an execution action.
    - The antigravity run logger associates a conversation identifier with a role slug.
    - The antigravity run logger converts a role label into a safe identifier string.

    GROUNDING_PROVISIONS:
    - action("record_log_event", None): Records an execution action event.
    - action("link_conversation_slug", None): Links conversation identifier to role slug.
    - action("sanitize_role_slug", str): Converts role label into safe identifier string.
    """

    @operation
    def log_event(self, event_name: str, source: str, summary: str) -> None:
        ...

    @operation
    def register_transcript(self, identifier: str, slug: str) -> None:
        ...

    @operation
    def sanitize_slug(self, label: str) -> str:
        ...
