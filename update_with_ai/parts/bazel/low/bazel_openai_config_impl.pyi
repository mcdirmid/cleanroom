# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 164998f2d2e0
# LOW_QA_AUDIT: 2026-10-09T21:19:01Z
# --- END CLEANROOM METADATA ---

"""Bazel OpenAI and runtime configuration implementation low-level specification."""

from typing import Optional
from framework import override, singleton_type
from support.lib.lifecycle import InTier, SystemTier
import agent_config
import dag_config
import openai_config


@singleton_type("system")
class AgentConfig(agent_config.AgentConfig, InTier[SystemTier]):
    """Loads agent execution parameters from target modules or environment defaults.

    GROUNDING:
    - Realizes agent_config by loading execution limits, step mode flags, and delta editing options via model_config_ext.
    """

    @property
    @override
    def conversation_limit(self) -> agent_config.ConversationLimit:
        """Reads maximum conversation turn limit.

        GROUNDING:
        - Reads the max conversation turn limit decoded from model config or environment defaults.
        """
        ...

    @property
    @override
    def inject_followups(self) -> bool:
        """Reads follow-up injection preference.

        GROUNDING:
        - Reads follow-up injection preference from model config or defaults to true.
        """
        ...

    @property
    @override
    def is_step_mode(self) -> bool:
        """Reads step mode permission.

        GROUNDING:
        - Reads step mode permission from model config or defaults to false.
        """
        ...

    @property
    @override
    def is_startup_reads(self) -> bool:
        """Reads startup file reading setting.

        GROUNDING:
        - Reads startup file reading setting from model config or defaults to true.
        """
        ...

    @property
    @override
    def edit_delta_output(self) -> bool:
        """Reads delta editing output preference.

        GROUNDING:
        - Reads delta editing output preference from model config or defaults to true.
        """
        ...

    @property
    @override
    def supersede_arg_keep(self) -> agent_config.SupersedeArgKeepLimit:
        """Reads trailing character retention limit.

        GROUNDING:
        - Reads trailing character retention limit from model config or defaults.
        """
        ...


@singleton_type("system")
class DagConfig(dag_config.DagConfig, InTier[SystemTier]):
    """Loads DAG traversal limits from target modules or environment defaults.

    GROUNDING:
    - Realizes dag_config by loading traversal visit bounds and batch size caps via model_config_ext.
    """

    @property
    @override
    def node_visit_limit(self) -> dag_config.NodeVisitLimit:
        """Reads maximum node visit cap.

        GROUNDING:
        - Reads maximum node visit cap from model config or defaults.
        """
        ...

    @property
    @override
    def batch_size(self) -> dag_config.BatchSize:
        """Reads maximum role batch size.

        GROUNDING:
        - Reads maximum role batch size from model config or defaults.
        """
        ...


@singleton_type("system")
class OpenAIConfig(openai_config.OpenAIConfig, InTier[SystemTier]):
    """Loads OpenAI connection and hyperparameter settings from target modules or environment variables.

    GROUNDING:
    - Realizes openai_config by extracting API endpoint parameters, timeouts, and authentication keys via model_config_ext.
    """

    @property
    @override
    def model_name(self) -> openai_config.ModelName:
        """Resolves model identifier string.

        GROUNDING:
        - Resolves model identifier string from model config target or default fallback.
        """
        ...

    @property
    @override
    def base_url(self) -> Optional[openai_config.BaseUrl]:
        """Resolves API endpoint base URL.

        GROUNDING:
        - Resolves API endpoint base URL when custom proxy routing is configured.
        """
        ...

    @property
    @override
    def api_key(self) -> Optional[openai_config.ApiKey]:
        """Extracts API authentication key.

        GROUNDING:
        - Extracts API authentication key from the designated process environment variable.
        """
        ...

    @property
    @override
    def timeout(self) -> openai_config.TimeoutSeconds:
        """Reads request timeout duration in seconds.

        GROUNDING:
        - Reads request timeout duration in seconds from model config.
        """
        ...

    @property
    @override
    def temperature(self) -> openai_config.Temperature:
        """Reads sampling temperature setting.

        GROUNDING:
        - Reads sampling temperature setting from model config.
        """
        ...

    @property
    @override
    def max_tokens(self) -> Optional[openai_config.MaxTokens]:
        """Reads maximum token generation ceiling.

        GROUNDING:
        - Reads maximum token generation ceiling from model config when specified.
        """
        ...
