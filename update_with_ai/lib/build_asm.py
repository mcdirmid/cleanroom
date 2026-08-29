"""
lib/build_asm.py

Assembly of the cleanroom components into the interface-only build runner.
"""

from __future__ import annotations

from .build_runner_impl import BuildRunnerImpl
from .build_graph_storage import GraphConfig
from .build_graph_storage_impl import BuildGraphStorageFileImpl
from .build_message_store_impl import BuildMessageStoreImpl
from .manifest_node_loader_impl import ManifestNodeLoaderImpl
from .runner_logger_impl import RunnerLoggerImpl
from .agent_node_clean_logic_asm import AgentNodeCleanLogicAsm
from .dag_cleaner_impl import DagCleanerImpl


class BuildAsm(BuildRunnerImpl):
    """
    Assembles the concrete implementations and sub-assemblies into BuildRunnerImpl
    (configuration and assembly only; no other functionality).
    """

    def __init__(self) -> None:
        message_store = BuildMessageStoreImpl()
        manifest_loader = ManifestNodeLoaderImpl()
        runner_logger = RunnerLoggerImpl()
        super().__init__(
            graph_factory=lambda config: BuildGraphStorageFileImpl(
                config=config,
                message_store=message_store,
                manifest_loader=manifest_loader,
            ),
            clean_logic_factory=lambda graph, ws_root, cfg_target, logger: (
                AgentNodeCleanLogicAsm(
                    graph=graph,
                    workspace_root=ws_root,
                    config_target=cfg_target,
                    logger=logger,
                )
            ),
            dag_factory=lambda graph, clean_logic: DagCleanerImpl(
                storage=graph, clean_logic=clean_logic
            ),
            runner_logger=runner_logger,
        )
