"""Loop grounding specification module."""

from __future__ import annotations
from dataclasses import dataclass
from typing import NewType, Protocol, Set
from support.lib.grounding_support import InTier, SystemTier, only_elem
from parts.dag.grounding import dag_storage

BuildSummary = NewType("BuildSummary", str)


@dataclass(frozen=True)
class BuildResult:
    """The final outcome of a cleaning pass.

    COVERED:
    - Encapsulates success boolean and summary description.
    """
    success: bool
    summary: BuildSummary


class Loop(InTier[SystemTier], Protocol):
    """System service executing topological build and cleaning passes across workspace nodes."""

    def clean_subgraph(self, target: dag_storage.DagNode) -> BuildResult:
        """
        COVERED:
        - MUST produce a build result upon pass completion.
          - Consequent knowledge: construct BuildResult record.

        DEFERRED:
        - MUST execute a cleaning pass over the acyclic subgraph rooted at the target node.
          - Deferred to refining implementation in bazel_loop_impl.py.
        """
        _result = BuildResult(success=True, summary=BuildSummary("pass"))
        raise NotImplementedError

    def mark_dirty(
        self, target: dag_storage.DagNode, message: dag_storage.ChangeMessage
    ) -> None:
        """
        COVERED:
        - MUST mark the target node dirty by injecting the change message into its pending messages.
          - Condition knowledge: resolve DagStorage collaborator.
          - Consequent knowledge: invoke storage.add_message(message, to=target).
        """
        storage: dag_storage.DagStorage = self.get_singleton(dag_storage.DagStorage)
        storage.add_message(message, to=target)
        raise NotImplementedError

    def inject_feedback(
        self, target: dag_storage.DagNode, message: dag_storage.FeedbackMessage
    ) -> None:
        """
        COVERED:
        - MUST inject the feedback message into the target node.
          - Condition knowledge: resolve DagStorage collaborator.
          - Consequent knowledge: invoke storage.add_message(message, to=target).
        """
        storage: dag_storage.DagStorage = self.get_singleton(dag_storage.DagStorage)
        storage.add_message(message, to=target)
        raise NotImplementedError

    def broadcast_change(
        self, source: dag_storage.DagNode, message: dag_storage.ChangeMessage
    ) -> None:
        """
        COVERED:
        - MUST broadcast the change message to all reverse dependencies of the node.
          - Condition knowledge: resolve DagStorage and query storage.get_dependents(source).
          - Consequent knowledge: invoke storage.add_message(message, to=dependent).        """
        storage: dag_storage.DagStorage = self.get_singleton(dag_storage.DagStorage)
        dependents: Set[dag_storage.DagNode] = storage.get_dependents(source)
        sample_dep: dag_storage.DagNode = only_elem(dependents)
        storage.add_message(message, to=sample_dep)
        raise NotImplementedError
