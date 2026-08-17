# lib/bazel_runner.py
"""
Interface LLS: bazel_runner

Bazel runner — assembler for running the cleanroom system.
Exposes the cleanroom system as a single entry point for running
a topological cleaning pass over a target node and its
transitive dependencies.

Library usage:
    from update_with_ai.lib.bazel_runner import BazRunner
    success, result = BazRunner().run_dag(root_node, workspace_root)

Script usage (CLI entry point):
    bazel run //pkg:target  # where target is a update_with_ai with clean target
"""

from __future__ import annotations
from typing import List, Optional, Protocol
from update_with_ai.lib.dag_storage import NodeId
from update_with_ai.lib.dag import CleaningResult


class BazRunner(Protocol):
    """Interface for assembling and running the cleanroom system."""

    def run_dag(
        self,
        root_node: NodeId,
        workspace_root: str,
        config_target: Optional[str] = None,
    ) -> CleaningResult:
        """
        Run a topological cleaning pass starting from root_node,
        producing output (changes or feedback) for all dirty nodes
        in the subgraph rooted at root_node.

        Args:
            root_node: Label of the root node to clean.
            workspace_root: Workspace/runfiles root for loading manifests.
            config_target: Optional agent_config target label (e.g.
                "//agent_configs:default") selecting the agent/model
                configuration; defaults to AGENT_CONFIG_TARGET then
                //agent_configs:default.

        Returns (True, CleanResult) on success (a ChangeResult,
        FeedbackResult, or NoChangeResult); (False, CleanResult) on failure
        (a FailureResult).
        """
        ...

    def inject_feedback(
        self,
        node_id: NodeId,
        workspace_root: str,
        messages: List[str],
    ) -> CleaningResult:
        """
        Deliver feedback messages to a node's own pending message store,
        marking the node dirty for a subsequent cleaning pass.

        Returns (True, CleanResult) on success (a NoChangeResult);
        (False, CleanResult) on failure (a FailureResult) if the node does
        not exist in the graph.
        """
        ...
