# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
# LAST_CHANGED: 2026-10-07T00:00:00Z
# CHANGE: new file
# CODE_HASH: b7ec4cfd3def
# LOW_QA_AUDIT: 2026-10-09T21:19:01Z
# --- END CLEANROOM METADATA ---

"""Cleanroom loop implementation low-level specification."""

from typing import Optional
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier, SystemTier
from update_with_ai.parts.dag.lib import dag_storage
from update_with_ai.parts.loop.lib import loop
import dag_storage
import loop_cleaner
import loop_node_cleaner
import runner_logger
import uv_manifest_loader


@singleton_type("system")
class Loop(loop.Loop, InTier[SystemTier]):
    """Realizes workspace target loading, topological cleaning, and runner telemetry streaming.

    GROUNDING:
    - Realizes loop interface contracts by loading targets into dag_storage via uv_manifest_loader, orchestrating cleaning with loop_cleaner, and reporting telemetry to runner_logger.
    """

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
        - WHEN node cleaning fails, MUST halt immediately with a failing build result.
        - WHEN any reachable node remains dirty after cleaning, MUST halt immediately with a failing build result.
        - WHEN an unexpected failure occurs during cleaning, MUST halt immediately with a failing build result.
        - WHEN producing a failing build result, MUST capture the failure reason in the build summary.
        - MUST stream telemetry capturing execution events to standard output.
        - MUST stream telemetry capturing execution events to transcript files.
        - MUST stream telemetry capturing pass duration to standard output and transcript files.
        - MUST stream telemetry capturing build outcome to standard output and transcript files.

        GROUNDING:
        - Loads target graph via uv_manifest_loader, invokes loop_cleaner to execute topological cleaning passes, checks post-cleaning dirtiness, and streams telemetry to runner_logger.
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

        GROUNDING:
        - Traverses subgraph via dag_storage, materializing templates for missing files and stamping clean metadata timestamps.
        """
        ...

    @operation
    @override
    def mark_dirty(
        self, target: dag_storage.DagNode, message: Optional[dag_storage.ChangeMessage] = ...
    ) -> None:
        """Marks a target node dirty by deleting its last cleaned timestamp.

        Args:
            target: The target node to mark dirty.
            message: Optional change message for backward compatibility.

        POSTCONDITIONS:
        - MUST delete the last cleaned timestamp from the target node source file metadata header.

        GROUNDING:
        - Delegates last cleaned timestamp removal to dag_storage.delete_last_cleaned.
        """
        ...

    @operation
    @override
    def inject_feedback(
        self, target: dag_storage.DagNode, message: dag_storage.FeedbackMessage
    ) -> None:
        """Injects caller feedback into target node source file metadata in graph storage.

        Args:
            target: The target node receiving feedback.
            message: The feedback message explaining defects detected.

        POSTCONDITIONS:
        - MUST inject caller-supplied feedback into the target node source file metadata in graph storage.
        - MUST identify the blamed dependency node in injected feedback.
        - MUST identify the diagnostic reason in injected feedback.

        GROUNDING:
        - Records feedback message on target node in dag_storage, updating in-band source headers with blamed dependency and diagnostic reasoning.
        """
        ...

    @operation
    @override
    def broadcast_change(
        self, source: dag_storage.DagNode, message: dag_storage.ChangeMessage
    ) -> None:
        """Broadcasts a change message across forward dependencies.

        GROUNDING:
        - Records change messages across forward dependencies in dag_storage.
        """
        ...

    @operation
    @override
    def record_change(
        self, target: dag_storage.DagNode, message: dag_storage.ChangeMessage
    ) -> None:
        """Records a change message against a target node in graph storage.

        Args:
            target: The target node recorded with changes.
            message: The change message informing of changes made.

        POSTCONDITIONS:
        - MUST record a caller-supplied change message against a target node in graph storage.
        - MUST clear the last cleaned timestamp of the target node in graph storage.
        - MUST update the change description of the target node in graph storage to dynamically invalidate downstream dependencies.

        GROUNDING:
        - Records change description on target node in dag_storage, clearing last cleaned timestamp and invalidating downstream dependents.
        """
        ...
