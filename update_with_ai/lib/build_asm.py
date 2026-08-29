"""
lib/build_asm.py

Assembly of the cleanroom components into the interface-only build runner.

Performs configuration and assembly only: subclasses BuildRunnerImpl and wires
the concrete implementations and sub-assemblies (file-backed graph storage,
agent clean logic assembly, DAG cleaner assembly) at construction.
Implements no functionality beyond assembly, and is never tested.

Library usage:
    from update_with_ai.lib.build_asm import BuildAsm
    runner = BuildAsm()
    success, err = runner.run_dag(root_node, workspace_root)
"""

from __future__ import annotations

from .build_runner_impl import BuildRunnerImpl
from .build_graph_storage import GraphConfig
from .build_graph_storage_impl import BuildGraphStorageFileImpl
from .agent_node_clean_logic_asm import AgentNodeCleanLogicAsm
from .dag_cleaner_asm import DagCleanerAsm


class BuildAsm(BuildRunnerImpl):
    """
    Assembles the concrete implementations and sub-assemblies into BuildRunnerImpl
    (configuration and assembly only; no other functionality).
    """

    def __init__(self) -> None:
        super().__init__(
            graph_factory=lambda config: BuildGraphStorageFileImpl(config=config),
            clean_logic_factory=lambda graph, ws_root, cfg_target, logger: (
                AgentNodeCleanLogicAsm(
                    graph=graph,
                    workspace_root=ws_root,
                    config_target=cfg_target,
                    logger=logger,
                )
            ),
            dag_factory=lambda graph, clean_logic: DagCleanerAsm(
                storage=graph, clean_logic=clean_logic
            ),
        )
