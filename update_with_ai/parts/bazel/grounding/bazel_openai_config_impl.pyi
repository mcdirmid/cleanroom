from typing import Optional, Self
from framework import override, singleton_type
import agent_config
import dag_config
import openai_config


@singleton_type('system')
class OpenaiConfig(openai_config.OpenaiConfig, agent_config.AgentConfig, dag_config.DagConfig):
    """Implements openai config, agent config, and dag config loaded from target module and environment credentials.

    REQUIREMENTS:
    - The openai config, agent config, and dag config resolve the target configuration from the MODEL_CONFIG_TARGET environment variable, the AGENT_CONFIG_TARGET environment variable, or the --config command-line argument, defaulting to the standard //model_configs:default target.
    - The openai config, agent config, and dag config load execution parameters and authentication credentials for language model agent runs from the target module.
    - When the target module is absent, execution parameters and authentication credentials fall back to ambient environment variables and standard defaults.

    GROUNDING_ARGUMENT:
    - As a system singleton, OpenaiConfig resolves execution parameters from static target configuration modules and environment variables using model_config_ext without requiring collaborator singleton services.
    """

    @property
    @override
    def model_name(self) -> str:
        """Target model identifier.

        GROUNDING_IMPLEMENTS:
        - knows("model_name", str): Exposes configured model name.
        """
        ...

    @property
    @override
    def base_url(self) -> Optional[str]:
        """Remote model API endpoint address.

        GROUNDING_IMPLEMENTS:
        - knows("base_url", Optional[str]): Exposes API endpoint address.
        """
        ...

    @property
    @override
    def api_key(self) -> Optional[str]:
        """Authentication credentials for the model API.

        GROUNDING_IMPLEMENTS:
        - knows("api_key", Optional[str]): Exposes API key.
        """
        ...

    @property
    @override
    def timeout(self) -> int:
        """Maximum duration in seconds permitted for a model request.

        GROUNDING_IMPLEMENTS:
        - knows("timeout", int): Exposes model request timeout in seconds.
        """
        ...

    @property
    @override
    def conversation_limit(self) -> agent_config.ConversationLimit:
        """Bound on the maximum number of model interaction turns.

        GROUNDING_IMPLEMENTS:
        - knows("conversation_limit", agent_config.ConversationLimit): Exposes turn limit.
        """
        ...

    @property
    @override
    def temperature(self) -> float:
        """Sampling temperature for model requests.

        GROUNDING_IMPLEMENTS:
        - knows("temperature", float): Exposes sampling temperature.
        """
        ...

    @property
    @override
    def max_tokens(self) -> Optional[int]:
        """Upper bound on generated response tokens per model interaction.

        GROUNDING_IMPLEMENTS:
        - knows("max_tokens", Optional[int]): Exposes max tokens upper bound.
        """
        ...

    @property
    @override
    def is_step_mode(self) -> bool:
        """Indicates whether the agent should use step mode to communicate a guide progressively.

        GROUNDING_IMPLEMENTS:
        - knows("is_step_mode", bool): Exposes whether step mode is configured.
        """
        ...

    @property
    @override
    def is_startup_reads(self) -> bool:
        """Indicates whether the agent should perform startup reads to inspect declared files at session start.

        GROUNDING_IMPLEMENTS:
        - knows("is_startup_reads", bool): Exposes whether startup reads are configured.
        """
        ...

    @property
    @override
    def inject_followups(self) -> bool:
        """Indicates whether the agent should inject followups to execute follow-up tool calls specified by tool responses.

        GROUNDING_IMPLEMENTS:
        - knows("inject_followups", bool): Exposes whether followups should be injected.
        """
        ...

    @property
    @override
    def edit_delta_output(self) -> bool:
        """Indicates whether editing tools should produce delta output.

        GROUNDING_IMPLEMENTS:
        - knows("edit_delta_output", bool): Exposes whether editing tools produce delta output.
        """
        ...

    @property
    @override
    def is_mcp_mode(self) -> bool:
        """Indicates whether the agent should operate in mcp mode.

        GROUNDING_IMPLEMENTS:
        - knows("is_mcp_mode", bool): Exposes whether mcp mode is active.
        """
        ...

    @property
    @override
    def node_visit_limit(self) -> dag_config.NodeVisitLimit:
        """Bound on the maximum number of times any node can be visited during dag cleaning.

        GROUNDING_IMPLEMENTS:
        - knows("node_visit_limit", dag_config.NodeVisitLimit): Exposes node visit limit.
        """
        ...

    @property
    @override
    def batch_size(self) -> dag_config.BatchSize:
        """Bound on the maximum number of dirty nodes of the same role processed together in an agent session.

        GROUNDING_IMPLEMENTS:
        - knows("batch_size", dag_config.BatchSize): Exposes batch size limit.
        """
        ...

    @property
    @override
    def supersede_arg_keep(self) -> int:
        """Trailing character retention limit for string arguments on superseded tool calls.

        GROUNDING_IMPLEMENTS:
        - knows("supersede_arg_keep", int): Exposes character retention limit for superseded tool calls.
        """
        ...



