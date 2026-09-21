# Requirements specified in mcp_config_impl.pyi
from __future__ import annotations
import os
from typing import Optional
from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    system,
)
from update_with_ai.parts.agent.lib import agent_config
from update_with_ai.parts.dag.lib import dag_config


class McpConfig(
    agent_config.AgentConfig,
    dag_config.DagConfig,
    Singleton,
):
    tier = system

    def __init__(self) -> None:
        raw_conv = os.environ.get("CONVERSATION_LIMIT") or os.environ.get("MODEL_CONVERSATION_LIMIT")
        self._conversation_limit = int(raw_conv) if raw_conv is not None else 50
        self._inject_followups = os.environ.get("INJECT_FOLLOWUPS", "false").lower() in ("true", "1")
        self._is_step_mode = (os.environ.get("STEP_MODE") or os.environ.get("CLEANROOM_STEP_MODE", "false")).lower() in ("true", "1")
        self._is_startup_reads = os.environ.get("STARTUP_READS", "false").lower() in ("true", "1")
        self._edit_delta_output = os.environ.get("EDIT_DELTA_OUTPUT", "false").lower() in ("true", "1")
        self._is_mcp_mode = (os.environ.get("MCP_MODE") or os.environ.get("CLEANROOM_MCP_MODE", "true")).lower() in ("true", "1")
        raw_nv = os.environ.get("NODE_VISIT_LIMIT")
        self._node_visit_limit = int(raw_nv) if raw_nv is not None else 500
        raw_bs = os.environ.get("BATCH_SIZE")
        self._batch_size = int(raw_bs) if raw_bs is not None else 1

    @property
    def conversation_limit(self) -> agent_config.ConversationLimit:
        return self._conversation_limit

    @property
    def inject_followups(self) -> bool:
        return self._inject_followups

    @property
    def is_step_mode(self) -> bool:
        return self._is_step_mode

    @property
    def is_startup_reads(self) -> bool:
        return self._is_startup_reads

    @property
    def edit_delta_output(self) -> bool:
        return self._edit_delta_output

    @property
    def is_mcp_mode(self) -> bool:
        return self._is_mcp_mode

    @is_mcp_mode.setter
    def is_mcp_mode(self, value: bool) -> None:
        self._is_mcp_mode = value

    @property
    def node_visit_limit(self) -> dag_config.NodeVisitLimit:
        return self._node_visit_limit

    @property
    def batch_size(self) -> dag_config.BatchSize:
        return self._batch_size


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        McpConfig,
        keys=[
            McpConfig,
            agent_config.AgentConfig,
            dag_config.DagConfig,
        ],
        tier=system,
    )

_initialize_ = __initialize__
