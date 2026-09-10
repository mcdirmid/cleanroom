"""Model configuration interface and data types."""

from typing import Optional, Protocol

ConversationLimit = int


class ModelConfig(Protocol):
    @property
    def model_name(self) -> str: ...

    @property
    def base_url(self) -> Optional[str]: ...

    @property
    def api_key(self) -> Optional[str]: ...

    @property
    def timeout(self) -> int: ...

    @property
    def conversation_limit(self) -> ConversationLimit: ...

    @property
    def temperature(self) -> float: ...

    @property
    def max_tokens(self) -> Optional[int]: ...

    @property
    def is_step_mode(self) -> bool: ...

    @property
    def is_startup_reads(self) -> bool: ...

    @property
    def inject_followups(self) -> bool: ...

