# Requirements specified in openai_config.pyi
"""OpenAI model configuration interface."""

from typing import Optional, Protocol


class OpenaiConfig(Protocol):
    @property
    def model_name(self) -> str: ...

    @property
    def base_url(self) -> Optional[str]: ...

    @property
    def api_key(self) -> Optional[str]: ...

    @property
    def timeout(self) -> int: ...

    @property
    def temperature(self) -> float: ...

    @property
    def max_tokens(self) -> Optional[int]: ...
