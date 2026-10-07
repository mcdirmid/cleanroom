# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T00:13:59Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: ddadca2dbf4a
# --- END CLEANROOM METADATA ---

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
    def mark_subgraph_clean(self, target: dag_storage.DagNode) -> None:
        """Marks all nodes in an acyclic subgraph clean, materializing missing templates and clearing unacted feedback.

        Args:
            target: The root target node in graph storage.

        POSTCONDITIONS:
        - MUST mark all nodes in the acyclic subgraph clean.
        - MUST materialize missing source files from declared templates.
        - MUST initialize timestamps and default change descriptions.
        - MUST clear unacted feedback across the subgraph.
        """
        ...

    @operation
    def mark_dirty(
        self, target: dag_storage.DagNode, message: dag_storage.ChangeMessage = ...
    ) -> None:
        """Marks a target node dirty by removing its last cleaned timestamp from in-band source metadata.

        Args:
            target: The target node to mark dirty.
            message: Optional change message for backward compatibility.

        POSTCONDITIONS:
        - MUST mark the target node dirty by removing its last cleaned timestamp from in-band source metadata.
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
        """Records a change message on a target node in graph storage, dynamically invalidating downstream dependencies.

        Args:
            source: The modified node.
            message: The change message informing of changes made.

        POSTCONDITIONS:
        - MUST mark the target node clean in graph storage with the change description from the change message.
        """
        ...

    @operation
    def record_change(
        self, target: dag_storage.DagNode, message: dag_storage.ChangeMessage
    ) -> None:
        """Records a change message on a target node in graph storage, dynamically invalidating downstream dependencies.

        Args:
            target: The modified node.
            message: The change message informing of changes made.

        POSTCONDITIONS:
        - MUST mark the target node clean in graph storage with the change description from the change message.
        """
        ...
