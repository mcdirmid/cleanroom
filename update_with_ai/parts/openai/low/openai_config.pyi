# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 3f30c8e6a791
# LOW_QA_AUDIT: 2026-10-09T21:19:01Z
# --- END CLEANROOM METADATA ---

"""OpenAI configuration low-level interface specification."""

from typing import NewType, Optional, Protocol
from framework import singleton_type
from support.lib.lifecycle import InTier, SystemTier

ModelName = NewType("ModelName", str)
BaseUrl = NewType("BaseUrl", str)
ApiKey = NewType("ApiKey", str)
TimeoutSeconds = NewType("TimeoutSeconds", float)
Temperature = NewType("Temperature", float)
MaxTokens = NewType("MaxTokens", int)


@singleton_type("system")
class OpenAIConfig(InTier[SystemTier], Protocol):
    """System service providing connection coordinates and model parameters for language model requests."""

    @property
    def model_name(self) -> ModelName:
        """Designates the target model."""
        ...

    @property
    def base_url(self) -> Optional[BaseUrl]:
        """Designates the remote model API endpoint address when custom routing applies."""
        ...

    @property
    def api_key(self) -> Optional[ApiKey]:
        """Provides authentication credentials when designated environment secrets apply."""
        ...

    @property
    def timeout(self) -> TimeoutSeconds:
        """Specifies the maximum duration in seconds permitted for a model request."""
        ...

    @property
    def temperature(self) -> Temperature:
        """Specifies the sampling temperature for model requests."""
        ...

    @property
    def max_tokens(self) -> Optional[MaxTokens]:
        """Upper bound specifying maximum response tokens permitted per request."""
        ...
