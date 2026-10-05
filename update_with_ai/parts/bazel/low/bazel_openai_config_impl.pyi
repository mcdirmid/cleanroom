# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T02:07:35Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 9961d17ce972
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
    """Loads agent execution parameters from target modules or environment defaults."""

    @property
    @override
    def conversation_limit(self) -> agent_config.ConversationLimit:
        ...

    @property
    @override
    def inject_followups(self) -> bool:
        ...

    @property
    @override
    def is_step_mode(self) -> bool:
        ...

    @property
    @override
    def is_startup_reads(self) -> bool:
        ...

    @property
    @override
    def edit_delta_output(self) -> bool:
        ...

    @property
    @override
    def is_mcp_mode(self) -> bool:
        ...

    @property
    @override
    def supersede_arg_keep(self) -> agent_config.SupersedeArgKeepLimit:
        ...


@singleton_type("system")
class DagConfig(dag_config.DagConfig, InTier[SystemTier]):
    """Loads DAG traversal limits from target modules or environment defaults."""

    @property
    @override
    def node_visit_limit(self) -> dag_config.NodeVisitLimit:
        ...

    @property
    @override
    def batch_size(self) -> dag_config.BatchSize:
        ...


@singleton_type("system")
class OpenAIConfig(openai_config.OpenAIConfig, InTier[SystemTier]):
    """Loads OpenAI connection and hyperparameter settings from target modules or environment variables."""

    @property
    @override
    def model_name(self) -> openai_config.ModelName:
        ...

    @property
    @override
    def base_url(self) -> Optional[openai_config.BaseUrl]:
        ...

    @property
    @override
    def api_key(self) -> Optional[openai_config.ApiKey]:
        ...

    @property
    @override
    def timeout(self) -> openai_config.TimeoutSeconds:
        ...

    @property
    @override
    def temperature(self) -> openai_config.Temperature:
        ...

    @property
    @override
    def max_tokens(self) -> Optional[openai_config.MaxTokens]:
        ...
