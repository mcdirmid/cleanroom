"""Loop low-level interface specification."""

from dataclasses import dataclass
from typing import NewType, Protocol
from framework import data_type, operation, singleton_type
from support.lib.lifecycle import InTier, SystemTier
import dag_storage

BuildSummary = NewType("BuildSummary", str)


@dataclass(frozen=True)
@data_type
class BuildResult:
    """The final outcome of a cleaning pass.

    Args:
        success: Whether the cleaning pass succeeded overall.
        summary: Diagnostic execution summary text.
    """
    success: bool
    summary: BuildSummary


@singleton_type("system")
class Loop(InTier[SystemTier], Protocol):
    """System service executing topological build and cleaning passes across workspace nodes."""

    @operation
    def clean_subgraph(self, target: dag_storage.DagNode) -> BuildResult:
        """Executes a cleaning pass over the acyclic subgraph rooted at a target node.

        Args:
            target: The root target node in graph storage.

        Returns:
            The final build result.

        POSTCONDITIONS:
        - MUST execute a cleaning pass over the acyclic subgraph rooted at the target node.
        - MUST produce a build result upon pass completion.
        """
        ...

    @operation
    def mark_dirty(
        self, target: dag_storage.DagNode, message: dag_storage.ChangeMessage
    ) -> None:
        """Marks a target node dirty by injecting a change message into its pending messages.

        Args:
            target: The target node to mark dirty.
            message: The change message explaining why the node requires cleaning.

        POSTCONDITIONS:
        - MUST mark the target node dirty by injecting the change message into its pending messages.
        """
        ...

    @operation
    def inject_feedback(
        self, target: dag_storage.DagNode, message: dag_storage.FeedbackMessage
    ) -> None:
        """Injects a feedback message into a target node.

        Args:
            target: The target node receiving the feedback.
            message: The feedback message explaining defects detected.

        POSTCONDITIONS:
        - MUST inject the feedback message into the target node.
        """
        ...

    @operation
    def broadcast_change(
        self, source: dag_storage.DagNode, message: dag_storage.ChangeMessage
    ) -> None:
        """Broadcasts a change message from a node to all of its reverse dependencies.

        Args:
            source: The modified node.
            message: The change message informing of changes made.

        POSTCONDITIONS:
        - MUST broadcast the change message to all reverse dependencies of the node.
        """
        ...
