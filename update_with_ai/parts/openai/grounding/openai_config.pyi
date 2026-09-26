from typing import Optional, Protocol
from framework import singleton_type

@singleton_type('system')
class OpenaiConfig(Protocol):
    """System service providing connection coordinates and model parameters for language model requests.

    REQUIREMENTS:
    - The openai config provides a model name designating the target model.
    - The openai config provides a base url designating the remote model API endpoint address when custom endpoint routing applies.
    - The openai config provides an api key providing authentication credentials when designated environment secrets apply.
    - The openai config provides a timeout specifying the maximum duration in seconds permitted for a model request.
    - The openai config provides a temperature specifying the sampling temperature for model requests.
    - The openai config provides a max tokens upper bound specifying the maximum number of response tokens permitted per request when token generation is constrained.

    GROUNDING_PROVISIONS:
    - knows("model_name", Self)
    - knows("base_url", Self)
    - knows("api_key", Self)
    - knows("timeout", Self)
    - knows("temperature", Self)
    - knows("max_tokens", Self)
    """

    @property
    def model_name(self) -> str:
        ...

    @property
    def base_url(self) -> Optional[str]:
        ...

    @property
    def api_key(self) -> Optional[str]:
        ...

    @property
    def timeout(self) -> int:
        ...

    @property
    def temperature(self) -> float:
        ...

    @property
    def max_tokens(self) -> Optional[int]:
        ...
