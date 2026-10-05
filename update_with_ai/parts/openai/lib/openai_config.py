# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T20:52:01Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: f6693dbab673
# --- END CLEANROOM METADATA ---

# Requirements specified in openai_config.pyi
from typing import NewType, Optional, Protocol

ModelName = NewType("ModelName", str)
BaseUrl = NewType("BaseUrl", str)
ApiKey = NewType("ApiKey", str)
TimeoutSeconds = NewType("TimeoutSeconds", float)
Temperature = NewType("Temperature", float)
MaxTokens = NewType("MaxTokens", int)


class OpenAIConfig(Protocol):
    @property
    def model_name(self) -> ModelName: ...

    @property
    def base_url(self) -> Optional[BaseUrl]: ...

    @property
    def api_key(self) -> Optional[ApiKey]: ...

    @property
    def timeout(self) -> TimeoutSeconds: ...

    @property
    def temperature(self) -> Temperature: ...

    @property
    def max_tokens(self) -> Optional[MaxTokens]: ...
