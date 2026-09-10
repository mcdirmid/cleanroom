from typing import Optional
from framework import override, singleton_type
import model_config

@singleton_type('system')
class ModelConfig(model_config.ModelConfig):
    """
PURPOSE:
Implements model config loaded from target module and environment credentials

FRESH_REQUIREMENTS:
- The model config resolves the target configuration from the MODEL_CONFIG_TARGET environment variable, the AGENT_CONFIG_TARGET environment variable, or the --config command-line argument, defaulting to the standard //model_configs:default target.
- The model config loads execution parameters from a target module located in the workspace runfiles tree or build output directory.

GROUNDING_ARGUMENT:
- As a system singleton, ModelConfig resolves execution parameters from static target configuration modules and environment variables using model_config_ext without requiring collaborator singleton services.
"""

    @property
    @override
    def model_name(self) -> str:
        """
PURPOSE:
Target model identifier

FRESH_REQUIREMENTS:
- The model config provides the model name resolved from the target module.

INHERITED_REQUIREMENTS:
- [ModelConfig] The model config provides a model name designating the target model.

GROUNDING_ARGUMENT:
- Loaded from external data source: target configuration module specified by MODEL_CONFIG_TARGET, AGENT_CONFIG_TARGET, or --config command-line argument via model_config_ext.
"""
        ...

    @property
    @override
    def base_url(self) -> Optional[str]:
        """
PURPOSE:
Remote model API endpoint address

FRESH_REQUIREMENTS:
- The model config provides the base url resolved from the target module.

INHERITED_REQUIREMENTS:
- [ModelConfig] The model config provides a base url designating the remote model API endpoint address, or absent if default address resolution applies.

GROUNDING_ARGUMENT:
- Loaded from external data source: target configuration module specified by MODEL_CONFIG_TARGET, AGENT_CONFIG_TARGET, or --config command-line argument via model_config_ext.
"""
        ...

    @property
    @override
    def api_key(self) -> Optional[str]:
        """
PURPOSE:
Authentication credentials for the model API

FRESH_REQUIREMENTS:
- The model config reads authentication credentials from the designated environment variable specified in the target module.

INHERITED_REQUIREMENTS:
- [ModelConfig] The model config provides an api key providing authentication credentials, or absent if ambient environment credentials apply.

GROUNDING_ARGUMENT:
- Loaded from external data source: environment variable designated by the target configuration module via model_config_ext.
"""
        ...

    @property
    @override
    def timeout(self) -> int:
        """
PURPOSE:
Maximum duration in seconds permitted for a model request

FRESH_REQUIREMENTS:
- The model config provides the timeout resolved from the target module.

INHERITED_REQUIREMENTS:
- [ModelConfig] The model config provides a timeout specifying the maximum duration in seconds permitted for a model request.

GROUNDING_ARGUMENT:
- Loaded from external data source: target configuration module specified by MODEL_CONFIG_TARGET, AGENT_CONFIG_TARGET, or --config command-line argument via model_config_ext.
"""
        ...

    @property
    @override
    def conversation_limit(self) -> model_config.ConversationLimit:
        """
PURPOSE:
Bound on the maximum number of model interaction turns

FRESH_REQUIREMENTS:
- The model config provides the conversation limit resolved from the target module.

INHERITED_REQUIREMENTS:
- [ModelConfig] The model config provides the conversation limit bounding interaction turns.

GROUNDING_ARGUMENT:
- Loaded from external data source: target configuration module specified by MODEL_CONFIG_TARGET, AGENT_CONFIG_TARGET, or --config command-line argument via model_config_ext.
"""
        ...

    @property
    @override
    def temperature(self) -> float:
        """
PURPOSE:
Sampling temperature for model requests

FRESH_REQUIREMENTS:
- The model config provides the temperature specifying the sampling temperature for model requests resolved from the target module.

INHERITED_REQUIREMENTS:
- [ModelConfig] The model config provides a temperature specifying the sampling temperature for model requests.

GROUNDING_ARGUMENT:
- Loaded from external data source: target configuration module specified by MODEL_CONFIG_TARGET, AGENT_CONFIG_TARGET, or --config command-line argument via model_config_ext.
"""
        ...

    @property
    @override
    def max_tokens(self) -> Optional[int]:
        """
PURPOSE:
Upper bound on generated response tokens per model interaction

FRESH_REQUIREMENTS:
- The model config provides the max tokens bound resolved from the target module.

INHERITED_REQUIREMENTS:
- [ModelConfig] The model config provides a max tokens upper bound specifying the maximum number of response tokens permitted per request, or absent if unconstrained.

GROUNDING_ARGUMENT:
- Loaded from external data source: target configuration module specified by MODEL_CONFIG_TARGET, AGENT_CONFIG_TARGET, or --config command-line argument via model_config_ext.
"""
        ...

    @property
    @override
    def is_step_mode(self) -> bool:
        """
PURPOSE:
Indicates whether the agent should use step mode to communicate a guide progressively

FRESH_REQUIREMENTS:
- The model config provides whether the agent should use step mode to communicate a guide progressively from the target module.

INHERITED_REQUIREMENTS:
- [ModelConfig] The model config provides whether the agent should use step mode to communicate a guide progressively.

GROUNDING_ARGUMENT:
- Loaded from external data source: target configuration module specified by MODEL_CONFIG_TARGET, AGENT_CONFIG_TARGET, or --config command-line argument via model_config_ext.
"""
        ...

    @property
    @override
    def is_startup_reads(self) -> bool:
        """
PURPOSE:
Indicates whether the agent should perform startup reads to inspect declared files at session start

FRESH_REQUIREMENTS:
- The model config provides whether the agent should perform startup reads to inspect declared files at session start from the target module.

INHERITED_REQUIREMENTS:
- [ModelConfig] The model config provides whether the agent should perform startup reads to inspect declared files at session start.

GROUNDING_ARGUMENT:
- Loaded from external data source: target configuration module specified by MODEL_CONFIG_TARGET, AGENT_CONFIG_TARGET, or --config command-line argument via model_config_ext.
"""
        ...

    @property
    @override
    def inject_followups(self) -> bool:
        """
PURPOSE:
Indicates whether the agent should inject followups to execute follow-up tool calls specified by tool responses

FRESH_REQUIREMENTS:
- The model config provides whether the agent should inject followups to execute follow-up tool calls specified by tool responses.

INHERITED_REQUIREMENTS:
- [ModelConfig] The model config provides whether the agent should inject followups to execute follow-up tool calls specified by tool responses.

GROUNDING_ARGUMENT:
- Loaded from external data source: target configuration module specified by MODEL_CONFIG_TARGET, AGENT_CONFIG_TARGET, or --config command-line argument via model_config_ext.
"""
        ...
