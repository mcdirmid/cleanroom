# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T02:07:35Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: dc7847e61160
# GROUNDING_QA_AUDIT: 2026-10-05T02:07:35Z
# --- END CLEANROOM METADATA ---

"""Loop grounding specification module."""

from __future__ import annotations
from dataclasses import dataclass
from typing import NewType, Protocol, Set, cast
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

    def mark_subgraph_clean(self, target: dag_storage.DagNode) -> None:
        """
        COVERED:
        - MUST mark all nodes in the acyclic subgraph clean.
        - MUST materialize missing source files from declared templates.
        - MUST initialize timestamps and default change descriptions.
        - MUST clear unacted feedback across the subgraph.
        """
        _target = target
        raise NotImplementedError

    def mark_dirty(
        self,
        target: dag_storage.DagNode,
        message: dag_storage.ChangeMessage = cast(dag_storage.ChangeMessage, None),
    ) -> None:
        """
        COVERED:
        - MUST mark the target node dirty by removing its last cleaned timestamp from in-band source metadata.
        """
        _target = target
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
        - MUST mark the target node clean in graph storage with the change description from the change message.
        """
        storage: dag_storage.DagStorage = self.get_singleton(dag_storage.DagStorage)
        storage.mark_node_clean(
            source, dag_storage.ChangeDescription(str(message.content))
        )
        raise NotImplementedError

    def record_change(
        self, target: dag_storage.DagNode, message: dag_storage.ChangeMessage
    ) -> None:
        """
        COVERED:
        - MUST mark the target node clean in graph storage with the change description from the change message.
        """
        storage: dag_storage.DagStorage = self.get_singleton(dag_storage.DagStorage)
        storage.mark_node_clean(
            target, dag_storage.ChangeDescription(str(message.content))
        )
        raise NotImplementedError
