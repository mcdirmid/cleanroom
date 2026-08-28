"""
lib/build_asm.py

Assembly of the cleanroom components into the interface-only build runner.

Performs configuration and assembly only: wires the concrete implementations
(file-backed graph storage, agent configuration loading, agent loop, sandbox,
agent clean logic, DAG cleaning) into a configured BuildRunnerImpl. Implements
no functionality beyond assembly, and is never tested.

Library usage:
    from update_with_ai.lib.build_asm import BuildAsm
    runner = BuildAsm().build()
    success, err = runner.run_dag(root_node, workspace_root)
"""

from __future__ import annotations

import dataclasses
from typing import Callable, Optional

from .build_runner_impl import BuildRunnerImpl
from .dag_cleaner import DagCleaner
from .dag_clean_logic import DagCleanLogic
from .build_graph_storage import BuildGraphStorage, GraphConfig
from .agent_loop import AgentLoop, LoggerCallback
from .build_agent_config import ConfigTarget
from .build_graph_storage_impl import BuildGraphStorageFileImpl
from .build_agent_config_impl import BuildAgentConfigImpl
from .agent_loop_config import AgentLoopConfig
from .agent_loop_impl import AgentLoopImpl
from .agent_node_clean_logic_impl import AgentNodeCleanLogicImpl
from .file_view import FileViewConfig
from .file_view_impl import FileViewImpl
from .guide_delivery import GuideDeliveryConfig
from .guide_delivery_impl import GuideDeliveryImpl
from .run_control import RunControlConfig
from .run_control_impl import RunControlImpl
from .sandbox import Sandbox, SandboxConfig
from .sandbox_impl import SandboxImpl
from .dag_cleaner_impl import DagCleanerImpl


class BuildAsm:
    """
    Assembles the concrete implementations into a configured interface-only
    BuildRunnerImpl (configuration and assembly only; no other functionality).
    """

    def build(self) -> BuildRunnerImpl:
        """Provide a configured interface-only runner (per the assembly LLS)."""

        def graph_factory(config: GraphConfig) -> BuildGraphStorage:
            """The file-backed graph and message store."""
            return BuildGraphStorageFileImpl(config=config)

        def clean_logic_factory(
            graph: BuildGraphStorage,
            workspace_root: str,
            config_target: Optional[ConfigTarget],
            logger: Optional[LoggerCallback],
        ) -> DagCleanLogic:
            """The agent clean logic for the run: resolve the agent
            configuration from the config target (argument, then
            AGENT_CONFIG_TARGET, then //agent_configs:default) with the API
            key resolved from the environment, build the agent loop and the
            sandbox factory (applying the configuration's sandbox gates to
            each node's sandbox), and construct the agent clean logic."""
            config_impl = BuildAgentConfigImpl()
            resolved_target = config_impl.resolve_config_target(config_target)
            agent_config = config_impl.load_config(resolved_target, workspace_root)
            api_key = config_impl.resolve_api_key(agent_config.api_key_env)
            agent_loop_config = agent_config.to_agent_loop_config(api_key)
            agent_loop = AgentLoopImpl(config=agent_loop_config)

            def make_sandbox(cfg: SandboxConfig) -> Sandbox:
                return SandboxImpl(
                    config=dataclasses.replace(
                        cfg,
                        session_start_reads_enabled=agent_config.session_start_reads,
                        step_sections_enabled=agent_config.step_sections,
                    ),
                    make_file_view=lambda fvc: FileViewImpl(config=fvc),
                    make_guide_delivery=lambda gdc: GuideDeliveryImpl(config=gdc),
                    make_run_control=lambda rcc, fv, gd: RunControlImpl(
                        rcc, file_view=fv, guide_delivery=gd
                    ),
                )

            def make_agent_loop(cfg: AgentLoopConfig) -> AgentLoop:
                return agent_loop

            return AgentNodeCleanLogicImpl(
                graph=graph,
                agent_loop_config=agent_loop_config,
                make_sandbox=make_sandbox,
                make_agent_loop=make_agent_loop,
                logger=logger,
            )

        def dag_factory(
            graph: BuildGraphStorage, clean_logic: DagCleanLogic
        ) -> DagCleaner:
            """The topological cleaner over the graph and the clean logic."""
            return DagCleanerImpl(storage=graph, clean_logic=clean_logic)

        return BuildRunnerImpl(
            graph_factory=graph_factory,
            clean_logic_factory=clean_logic_factory,
            dag_factory=dag_factory,
        )
