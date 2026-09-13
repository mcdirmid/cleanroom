from typing import Optional, Protocol
from framework import singleton_type

@singleton_type('system')
class OpenaiConfig(Protocol):
    """
PURPOSE:
Defined as a system service providing connection coordinates and model parameters for language model requests
"""

    @property
    def model_name(self) -> str:
        """
PURPOSE:
Target model identifier

FRESH_REQUIREMENTS:
- The openai config provides a model name designating the target model.
"""
        ...

    @property
    def base_url(self) -> Optional[str]:
        """
PURPOSE:
Remote model API endpoint address

FRESH_REQUIREMENTS:
- The openai config provides a base url designating the remote model API endpoint address when custom endpoint routing applies.
"""
        ...

    @property
    def api_key(self) -> Optional[str]:
        """
PURPOSE:
Authentication credentials for the model API

FRESH_REQUIREMENTS:
- The openai config provides an api key providing authentication credentials when designated environment secrets apply.
"""
        ...

    @property
    def timeout(self) -> int:
        """
PURPOSE:
Maximum duration in seconds permitted for a model request

FRESH_REQUIREMENTS:
- The openai config provides a timeout specifying the maximum duration in seconds permitted for a model request.
"""
        ...

    @property
    def temperature(self) -> float:
        """
PURPOSE:
Sampling temperature for model requests

FRESH_REQUIREMENTS:
- The openai config provides a temperature specifying the sampling temperature for model requests.
"""
        ...

    @property
    def max_tokens(self) -> Optional[int]:
        """
PURPOSE:
Upper bound on generated response tokens per model interaction

FRESH_REQUIREMENTS:
- The openai config provides a max tokens upper bound specifying the maximum number of response tokens permitted per request when token generation is constrained.
"""
        ...
