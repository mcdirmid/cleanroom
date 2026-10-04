"""Bazel loop implementation low-level specification."""

from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier, SystemTier
import dag_storage
import loop


@singleton_type("system")
class Loop(loop.Loop, InTier[SystemTier]):
    """Realizes workspace target loading, topological cleaning, and runner telemetry streaming."""

    @operation
    @override
    def clean_subgraph(self, target: dag_storage.DagNode) -> loop.BuildResult:
        """Executes a cleaning pass over the target subgraph.

        Args:
            target: The root target node of the execution pass.

        Returns:
            The overall build outcome result.

        POSTCONDITIONS:
        - MUST resolve target labels against workspace directories to populate graph storage when executing a cleaning pass.
        - MUST resolve target labels against runfiles trees to populate graph storage when executing a cleaning pass.
        - WHEN node cleaning fails, MUST halt immediately with a failing build result.
        - WHEN any reachable node remains dirty after cleaning, MUST halt immediately with a failing build result.
        - WHEN an unexpected failure occurs during cleaning, MUST halt immediately with a failing build result.
        - WHEN producing a failing build result, MUST capture the failure reason in the build summary.
        - MUST stream telemetry capturing execution events to standard output.
        - MUST stream telemetry capturing execution events to transcript files.
        - MUST stream telemetry capturing pass duration to standard output and transcript files.
        - MUST stream telemetry capturing build outcome to standard output and transcript files.
        """
        ...

    @operation
    @override
    def mark_subgraph_clean(self, target: dag_storage.DagNode) -> None:
        """Marks all nodes in an acyclic subgraph clean, materializing missing templates and clearing unacted feedback.

        Args:
            target: The root target node in graph storage.

        POSTCONDITIONS:
        - MUST materialize missing source files across the target subgraph from declared templates.
        - MUST stamp node metadata headers with the current timestamp as the last cleaned timestamp.
        - MUST initialize missing last changed timestamps and default change descriptions.
        - MUST clear unacted feedback across the target subgraph.
        """
        ...

    @operation
    @override
    def mark_dirty(
        self, target: dag_storage.DagNode, message: dag_storage.ChangeMessage = ...
    ) -> None:
        """Marks a target node dirty by deleting its last cleaned timestamp.

        Args:
            target: The target node to mark dirty.
            message: Optional change message for backward compatibility.

        POSTCONDITIONS:
        - MUST delete the last cleaned timestamp from the target node source file metadata header.
        """
        ...

    @operation
    @override
    def inject_feedback(
        self, target: dag_storage.DagNode, message: dag_storage.FeedbackMessage
    ) -> None:
        ...

    @operation
    @override
    def broadcast_change(
        self, source: dag_storage.DagNode, message: dag_storage.ChangeMessage
    ) -> None:
        ...

