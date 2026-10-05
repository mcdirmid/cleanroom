# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T20:52:01Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: ec819d9d6ab6
# GROUNDING_QA_AUDIT: 2026-10-05T20:52:01Z
# --- END CLEANROOM METADATA ---

"""OpenAI configuration grounding specification module."""

from __future__ import annotations
from typing import NewType, Optional, Protocol
from support.lib.grounding_support import InTier, SystemTier

ModelName = NewType("ModelName", str)
BaseUrl = NewType("BaseUrl", str)
ApiKey = NewType("ApiKey", str)
TimeoutSeconds = NewType("TimeoutSeconds", float)
Temperature = NewType("Temperature", float)
MaxTokens = NewType("MaxTokens", int)


class OpenAIConfig(InTier[SystemTier], Protocol):
    """System service providing connection coordinates and model parameters for language model requests."""

    @property
    def model_name(self) -> ModelName:
        """
        DEFERRED:
        - Model name identifier for language model requests.
        """
        raise NotImplementedError

    @property
    def base_url(self) -> Optional[BaseUrl]:
        """
        DEFERRED:
        - Base URL endpoint for language model requests.
        """
        raise NotImplementedError

    @property
    def api_key(self) -> Optional[ApiKey]:
        """
        DEFERRED:
        - Authentication key for language model requests.
        """
        raise NotImplementedError

    @property
    def timeout(self) -> TimeoutSeconds:
        """
        DEFERRED:
        - Request timeout limit in seconds.
        """
        raise NotImplementedError

    @property
    def temperature(self) -> Temperature:
        """
        DEFERRED:
        - Sampling temperature parameter for model responses.
        """
        raise NotImplementedError

    @property
    def max_tokens(self) -> Optional[MaxTokens]:
        """
        DEFERRED:
        - Maximum token generation limit for model responses.
        """
        raise NotImplementedError
