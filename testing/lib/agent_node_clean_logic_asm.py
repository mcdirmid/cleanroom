"""
lib/agent_node_clean_logic_asm.py

Assembly of the agent node clean logic component.

Performs configuration and assembly only: subclasses AgentNodeCleanLogicImpl,
wiring BuildAgentConfigImpl, AgentLoopImpl, and SandboxAsm at construction.
Implements no functionality beyond assembly, and is never tested.

Library usage:
    from testing.lib.agent_node_clean_logic_asm import AgentNodeCleanLogicAsm
    clean_logic = AgentNodeCleanLogicAsm(graph, workspace_root, config_target, logger)
"""

from __future__ import annotations

import dataclasses
from typing import Optional

from .build_graph_storage import BuildGraphStorage
from .build_agent_config import ConfigTarget
from .build_agent_config_impl import BuildAgentConfigImpl
from .agent_loop import LoggerCallback
from .agent_loop_impl import AgentLoopImpl
from .agent_node_clean_logic_impl import AgentNodeCleanLogicImpl
from .sandbox import SandboxConfig
from .sandbox_asm import SandboxAsm


class AgentNodeCleanLogicAsm(AgentNodeCleanLogicImpl):
    """
    Assembles concrete agent execution and configuration components into
    AgentNodeCleanLogicImpl (configuration and assembly only; no other
    functionality).
    """

    def __init__(
        self,
        graph: BuildGraphStorage,
        workspace_root: str,
        config_target: Optional[ConfigTarget] = None,
        logger: Optional[LoggerCallback] = None,
    ) -> None:
        config_impl = BuildAgentConfigImpl()
        resolved_target = config_impl.resolve_config_target(config_target)
        agent_config = config_impl.load_config(resolved_target, workspace_root)
        api_key = config_impl.resolve_api_key(agent_config.api_key_env)
        agent_loop_config = agent_config.to_agent_loop_config(api_key)
        agent_loop = AgentLoopImpl(config=agent_loop_config)

        super().__init__(
            graph=graph,
            agent_loop_config=agent_loop_config,
            make_sandbox=lambda cfg: SandboxAsm(
                config=dataclasses.replace(
                    cfg,
                    session_start_reads_enabled=agent_config.session_start_reads,
                    step_sections_enabled=agent_config.step_sections,
                )
            ),
            make_agent_loop=lambda cfg: agent_loop,
            logger=logger,
        )
