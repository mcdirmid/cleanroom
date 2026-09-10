from typing import Optional, Protocol
from framework import data_type, singleton_type

@data_type
class ConversationLimit(int):
    """
PURPOSE:
Bound on the maximum number of model interaction turns permitted
"""
    ...

@singleton_type('system')
class ModelConfig(Protocol):
    """
PURPOSE:
Defined as a system service providing execution parameters for agent runs
"""

    @property
    def model_name(self) -> str:
        """
PURPOSE:
Target model identifier

FRESH_REQUIREMENTS:
- The model config provides a model name designating the target model.
"""
        ...

    @property
    def base_url(self) -> Optional[str]:
        """
PURPOSE:
Remote model API endpoint address

FRESH_REQUIREMENTS:
- The model config provides a base url designating the remote model API endpoint address, or absent if default address resolution applies.
"""
        ...

    @property
    def api_key(self) -> Optional[str]:
        """
PURPOSE:
Authentication credentials for the model API

FRESH_REQUIREMENTS:
- The model config provides an api key providing authentication credentials, or absent if ambient environment credentials apply.
"""
        ...

    @property
    def timeout(self) -> int:
        """
PURPOSE:
Maximum duration in seconds permitted for a model request

FRESH_REQUIREMENTS:
- The model config provides a timeout specifying the maximum duration in seconds permitted for a model request.
"""
        ...

    @property
    def conversation_limit(self) -> ConversationLimit:
        """
PURPOSE:
Bound on the maximum number of model interaction turns

FRESH_REQUIREMENTS:
- The model config provides the conversation limit bounding interaction turns.
"""
        ...

    @property
    def temperature(self) -> float:
        """
PURPOSE:
Sampling temperature for model requests

FRESH_REQUIREMENTS:
- The model config provides a temperature specifying the sampling temperature for model requests.
"""
        ...

    @property
    def max_tokens(self) -> Optional[int]:
        """
PURPOSE:
Upper bound on generated response tokens per model interaction

FRESH_REQUIREMENTS:
- The model config provides a max tokens upper bound specifying the maximum number of response tokens permitted per request, or absent if unconstrained.
"""
        ...

    @property
    def is_step_mode(self) -> bool:
        """
PURPOSE:
Indicates whether the agent should use step mode to communicate a guide progressively

FRESH_REQUIREMENTS:
- The model config provides whether the agent should use step mode to communicate a guide progressively.
"""
        ...

    @property
    def is_startup_reads(self) -> bool:
        """
PURPOSE:
Indicates whether the agent should perform startup reads to inspect declared files at session start

FRESH_REQUIREMENTS:
- The model config provides whether the agent should perform startup reads to inspect declared files at session start.
"""
        ...

    @property
    def inject_followups(self) -> bool:
        """
PURPOSE:
Indicates whether the agent should inject followups to execute follow-up tool calls specified by tool responses

FRESH_REQUIREMENTS:
- The model config provides whether the agent should inject followups to execute follow-up tool calls specified by tool responses.
"""
        ...
