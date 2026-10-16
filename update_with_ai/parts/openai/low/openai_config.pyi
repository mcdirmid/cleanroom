# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:46Z
# LAST_CHANGED: 2026-10-11T03:37:03Z
# CHANGE: Add conditional endpoint, credential, and token bound contracts
# CODE_HASH: fdd074302969
# SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
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
        """Designates the remote model API endpoint address when custom routing applies.

        POSTCONDITIONS:
        - WHEN custom endpoint routing applies, MUST provide the remote model endpoint address.
        """
        ...

    @property
    def api_key(self) -> Optional[ApiKey]:
        """Provides authentication credentials when designated environment secrets apply.

        POSTCONDITIONS:
        - WHEN designated environment secrets apply, MUST provide the authentication credentials.
        """
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
        """Upper bound specifying maximum response tokens permitted per request.

        POSTCONDITIONS:
        - WHEN token generation is constrained, MUST provide the max tokens upper bound.
        """
        ...
