from support.lib.lifecycle import Singleton, SystemTier
# Requirements specified in openai_config.pyi
from typing import NewType, Optional, Protocol

ModelName = NewType("ModelName", str)
BaseUrl = NewType("BaseUrl", str)
ApiKey = NewType("ApiKey", str)
TimeoutSeconds = NewType("TimeoutSeconds", float)
Temperature = NewType("Temperature", float)
MaxTokens = NewType("MaxTokens", int)


# Contract: OpenAIConfig provides connection coordinates and model parameters for language model requests.
class OpenAIConfig(Singleton[SystemTier], Protocol):
    # Contract: Designates the target model.
    @property
    def model_name(self) -> ModelName: ...

    # Contract: Designates the remote model API endpoint address when custom routing applies.
    @property
    def base_url(self) -> Optional[BaseUrl]: ...

    # Contract: Provides authentication credentials when designated environment secrets apply.
    @property
    def api_key(self) -> Optional[ApiKey]: ...

    # Contract: Specifies the maximum duration in seconds permitted for a model request.
    @property
    def timeout(self) -> TimeoutSeconds: ...

    # Contract: Specifies the sampling temperature for model requests.
    @property
    def temperature(self) -> Temperature: ...

    # Contract: Upper bound specifying maximum response tokens permitted per request.
    @property
    def max_tokens(self) -> Optional[MaxTokens]: ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# --- END CLEANROOM METADATA ---
