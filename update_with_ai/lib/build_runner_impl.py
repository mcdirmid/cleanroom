# lib/build_runner_impl.py
"""
Build runner — interface-only implementation of the build_runner interface.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, TypeAlias

from .build_runner import BuildRunner
from .dag_storage import NodeId, NodeMessage
from .dag_cleaner import DagCleaner, CleaningResult
from .dag_clean_logic import (
    CleanResult,
    ChangeResult,
    FeedbackResult,
    NoChangeResult,
    FailureResult,
    DagCleanLogic,
)
from .build_graph_storage import BuildGraphStorage, GraphConfig
from .agent_loop import LoggerCallback
from .build_agent_config import ConfigTarget
from .runner_logger import RunnerLogger

CleanLogicFactory: TypeAlias = Callable[
    [BuildGraphStorage, str, Optional[ConfigTarget], Optional[LoggerCallback]],
    DagCleanLogic,
]


class BuildRunnerImpl(BuildRunner):
    """
    Interface-only implementation of the build_runner interface.
    """

    def __init__(
        self,
        graph_factory: Callable[[GraphConfig], BuildGraphStorage],
        clean_logic_factory: CleanLogicFactory,
        dag_factory: Callable[[BuildGraphStorage, DagCleanLogic], DagCleaner],
        runner_logger: RunnerLogger,
    ) -> None:
        self._graph_factory = graph_factory
        self._clean_logic_factory = clean_logic_factory
        self._dag_factory = dag_factory
        self._runner_logger: RunnerLogger = runner_logger

    def run_dag(
        self,
        root_node: NodeId,
        workspace_root: str,
        config_target: Optional[str] = None,
    ) -> CleaningResult:
        print(f"Loading graph from {root_node}...")
        graph = self._graph_factory(GraphConfig(workspace_root=workspace_root))

        log_path = self._runner_logger.resolve_log_path()
        print(f"Agent log: {log_path}")
        agent_logger, log_closer = self._runner_logger.create_agent_logger(log_path)

        clean_logic = self._clean_logic_factory(
            graph, workspace_root, config_target, agent_logger
        )
        dag_cleaner = self._dag_factory(graph, clean_logic)

        print(f"\nRunning DAG from {root_node}...")
        try:
            result = dag_cleaner.clean_subgraph(root_node)
        finally:
            log_closer()

        print(f"Full agent transcript: {log_path}")
        print(f"DAG result: {result}")
        return result

    def inject_feedback(
        self,
        node_id: NodeId,
        workspace_root: str,
        messages: List[str],
    ) -> CleaningResult:
        print(f"Loading graph from {node_id}...")
        graph = self._graph_factory(GraphConfig(workspace_root=workspace_root))

        try:
            graph.resolve_package_directory(node_id)
        except ValueError:
            return (False, FailureResult())

        graph.add_messages(
            node_id,
            [NodeMessage(kind="feedback", text=m) for m in messages],
        )
        for message in messages:
            print(f"Delivered feedback to {node_id}: {message}")
        return (True, NoChangeResult())

    def add_change(
        self,
        node_id: NodeId,
        workspace_root: str,
        change: str = "check",
    ) -> CleaningResult:
        print(f"Loading graph from {node_id}...")
        graph = self._graph_factory(GraphConfig(workspace_root=workspace_root))

        try:
            graph.resolve_package_directory(node_id)
        except ValueError:
            return (False, FailureResult())

        graph.add_messages(node_id, [NodeMessage(kind="change", text=change)])
        print(f"Delivered change to {node_id}: {change}")
        return (True, NoChangeResult())

    def broadcast_change(
        self,
        node_id: NodeId,
        workspace_root: str,
        change: str,
    ) -> CleaningResult:
        print(f"Loading graph from {node_id}...")
        graph = self._graph_factory(GraphConfig(workspace_root=workspace_root))

        try:
            graph.resolve_package_directory(node_id)
        except ValueError:
            return (False, FailureResult())

        writable = graph.resolve_node_definition(node_id).sandbox_config.writable_paths
        src = writable[0] if writable else ""
        message_text = "{}: {}".format(src, change) if src else change
        broadcast = [NodeMessage(kind="change", text=message_text)]
        for target in graph.get_known_reverse_dependencies(node_id):
            try:
                graph.add_messages(target, broadcast)
            except ValueError:
                continue
        graph.delete_node_data(node_id)
        print(
            f"Broadcast change from {node_id} to its reverse dependencies: "
            f"{message_text}"
        )
        return (True, NoChangeResult())
