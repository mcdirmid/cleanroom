from typing import Optional
from framework import override, singleton_type
import agent_config
import dag_config
import openai_config

@singleton_type('system')
class ModelConfig(agent_config.AgentConfig, dag_config.DagConfig, openai_config.OpenaiConfig):
    """
PURPOSE:
Implements openai config, agent config, and dag config loaded from target module and environment credentials

FRESH_REQUIREMENTS:
- The openai config, agent config, and dag config resolve the target configuration from the MODEL_CONFIG_TARGET environment variable, the AGENT_CONFIG_TARGET environment variable, or the --config command-line argument, defaulting to the standard //model_configs:default target.
- The openai config, agent config, and dag config load execution parameters and authentication credentials for language model agent runs from the target module.

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
- The openai config provides the model name designating the target model.

INHERITED_REQUIREMENTS:
- [OpenaiConfig] The openai config provides a model name designating the target model.

GROUNDING_ARGUMENT:
- Resolved from the target configuration module located in the workspace runfiles tree or build output directory via model_config_ext.
"""
        ...

    @property
    @override
    def base_url(self) -> Optional[str]:
        """
PURPOSE:
Remote model API endpoint address

FRESH_REQUIREMENTS:
- The openai config provides the base url designating the remote model API endpoint address.

INHERITED_REQUIREMENTS:
- [OpenaiConfig] The openai config provides a base url designating the remote model API endpoint address when custom endpoint routing applies.

GROUNDING_ARGUMENT:
- Resolved from the target configuration module located in the workspace runfiles tree or build output directory via model_config_ext.
"""
        ...

    @property
    @override
    def api_key(self) -> Optional[str]:
        """
PURPOSE:
Authentication credentials for the model API

FRESH_REQUIREMENTS:
- The openai config provides the api key providing authentication credentials from the designated environment variable, or ambient environment credentials.

INHERITED_REQUIREMENTS:
- [OpenaiConfig] The openai config provides an api key providing authentication credentials when designated environment secrets apply.

GROUNDING_ARGUMENT:
- Resolved from the designated environment variable specified in the target module via model_config_ext.
"""
        ...

    @property
    @override
    def timeout(self) -> int:
        """
PURPOSE:
Maximum duration in seconds permitted for a model request

FRESH_REQUIREMENTS:
- The openai config provides the timeout specifying the maximum request duration in seconds.

INHERITED_REQUIREMENTS:
- [OpenaiConfig] The openai config provides a timeout specifying the maximum duration in seconds permitted for a model request.

GROUNDING_ARGUMENT:
- Resolved from the target configuration module located in the workspace runfiles tree or build output directory via model_config_ext.
"""
        ...

    @property
    @override
    def conversation_limit(self) -> agent_config.ConversationLimit:
        """
PURPOSE:
Bound on the maximum number of model interaction turns

FRESH_REQUIREMENTS:
- The agent config provides the conversation limit bounding interaction turns.

INHERITED_REQUIREMENTS:
- [AgentConfig] The agent config provides the conversation limit bounding interaction turns.

GROUNDING_ARGUMENT:
- Resolved from the target configuration module located in the workspace runfiles tree or build output directory via model_config_ext.
"""
        ...

    @property
    @override
    def temperature(self) -> float:
        """
PURPOSE:
Sampling temperature for model requests

FRESH_REQUIREMENTS:
- The openai config provides the temperature specifying the sampling temperature for model requests.

INHERITED_REQUIREMENTS:
- [OpenaiConfig] The openai config provides a temperature specifying the sampling temperature for model requests.

GROUNDING_ARGUMENT:
- Resolved from the target configuration module located in the workspace runfiles tree or build output directory via model_config_ext.
"""
        ...

    @property
    @override
    def max_tokens(self) -> Optional[int]:
        """
PURPOSE:
Upper bound on generated response tokens per model interaction

FRESH_REQUIREMENTS:
- The openai config provides the max tokens bound resolved from the target module when token generation is constrained.

INHERITED_REQUIREMENTS:
- [OpenaiConfig] The openai config provides a max tokens upper bound specifying the maximum number of response tokens permitted per request when token generation is constrained.

GROUNDING_ARGUMENT:
- Resolved from the target configuration module located in the workspace runfiles tree or build output directory via model_config_ext.
"""
        ...

    @property
    @override
    def is_step_mode(self) -> bool:
        """
PURPOSE:
Indicates whether the agent should use step mode to communicate a guide progressively

FRESH_REQUIREMENTS:
- The agent config provides whether the agent should use step mode to communicate a guide progressively.

INHERITED_REQUIREMENTS:
- [AgentConfig] The agent config provides whether the agent should use step mode to communicate a guide progressively.

GROUNDING_ARGUMENT:
- Resolved from the target configuration module located in the workspace runfiles tree or build output directory via model_config_ext.
"""
        ...

    @property
    @override
    def is_startup_reads(self) -> bool:
        """
PURPOSE:
Indicates whether the agent should perform startup reads to inspect declared files at session start

FRESH_REQUIREMENTS:
- The agent config provides whether the agent should perform startup reads to inspect declared files at session start.

INHERITED_REQUIREMENTS:
- [AgentConfig] The agent config provides whether the agent should perform startup reads to inspect declared files at session start.

GROUNDING_ARGUMENT:
- Resolved from the target configuration module located in the workspace runfiles tree or build output directory via model_config_ext.
"""
        ...

    @property
    @override
    def inject_followups(self) -> bool:
        """
PURPOSE:
Indicates whether the agent should inject followups to execute follow-up tool calls specified by tool responses

FRESH_REQUIREMENTS:
- The agent config provides whether the agent should inject followups to execute follow-up tool calls specified by tool responses.

INHERITED_REQUIREMENTS:
- [AgentConfig] The agent config provides whether the agent should inject followups to execute follow-up tool calls specified by tool responses.

GROUNDING_ARGUMENT:
- Resolved from the target configuration module located in the workspace runfiles tree or build output directory via model_config_ext.
"""
        ...

    @property
    @override
    def edit_delta_output(self) -> bool:
        """
PURPOSE:
Indicates whether editing tools should produce delta output

FRESH_REQUIREMENTS:
- Whether editing tools should produce delta output.

INHERITED_REQUIREMENTS:
- [AgentConfig] The agent config provides whether editing tools should produce delta output.

GROUNDING_ARGUMENT:
- Resolved from the target configuration module located in the workspace runfiles tree or build output directory via model_config_ext.
"""
        ...

    @property
    @override
    def node_visit_limit(self) -> dag_config.NodeVisitLimit:
        """
PURPOSE:
Bound on the maximum number of times any node can be visited during dag cleaning

FRESH_REQUIREMENTS:
- The dag config provides the node visit limit bounding node visits during graph cleaning.

INHERITED_REQUIREMENTS:
- [DagConfig] The dag config provides the node visit limit bounding node visits during graph cleaning.

GROUNDING_ARGUMENT:
- Resolved from the target configuration module located in the workspace runfiles tree or build output directory via model_config_ext.
"""
        ...

    @property
    @override
    def batch_size(self) -> dag_config.BatchSize:
        """
PURPOSE:
Bound on the maximum number of dirty nodes of the same role processed together in an agent session

FRESH_REQUIREMENTS:
- The dag config provides the batch size bounding dirty nodes processed together in an agent session.

INHERITED_REQUIREMENTS:
- [DagConfig] The dag config provides the batch size bounding dirty nodes processed together in an agent session.

GROUNDING_ARGUMENT:
- Resolved from the target configuration module located in the workspace runfiles tree or build output directory via model_config_ext.
"""
        ...
