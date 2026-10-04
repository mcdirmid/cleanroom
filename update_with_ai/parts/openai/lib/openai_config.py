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
