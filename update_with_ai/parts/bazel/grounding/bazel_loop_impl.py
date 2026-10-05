# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T06:13:26Z
# LAST_CHANGED: 2026-10-05T06:13:26Z
# CHANGE: Align inject_feedback and record_change with low-level contract
# CODE_HASH: c363a35405e5
# --- END CLEANROOM METADATA ---

"""Bazel loop implementation grounding specification module."""

from __future__ import annotations
from typing import Optional, Set, cast
from support.lib.grounding_support import InTier, SystemTier, only_elem
from parts.core.grounding import runner_logger
from parts.dag.grounding import dag_storage, dag_subgraph
from parts.loop.grounding import loop, loop_cleaner, loop_node_cleaner
from parts.bazel.grounding import bazel_manifest_loader


class Loop(loop.Loop, InTier[SystemTier]):
    """Realizes workspace target loading, topological cleaning, and runner telemetry streaming.

    DISCHARGED:
    - clean_subgraph: Discharges manifest loading, cleaning loop orchestration, and telemetry streaming.
    - mark_dirty / inject_feedback / broadcast_change / record_change: Discharges message routing across graph storage.
    """

    def clean_subgraph(self, target: dag_storage.DagNode) -> loop.BuildResult:
        """
        COVERED:
        - MUST resolve target labels against workspace directories to populate graph storage when executing a cleaning pass.
          - Condition knowledge: resolve BazelManifestLoader, invoke loader.load_manifest(target).
        - MUST resolve target labels against runfiles trees to populate graph storage when executing a cleaning pass.
          - Consequent knowledge: populates graph storage from manifest definitions.
        - WHEN node cleaning fails, MUST halt immediately with a failing build result.
          - Condition knowledge: evaluate not clean_ok.
          - Consequent knowledge: return BuildResult(success=False, summary=BuildSummary("Node cleaner failed to clean target")).
        - WHEN any reachable node remains dirty after cleaning, MUST halt immediately with a failing build result.
          - Condition knowledge: evaluate not subgraph.is_complete().
          - Consequent knowledge: return BuildResult(success=False, summary=BuildSummary("Reachable nodes remain dirty after cleaning pass")).
        - WHEN an unexpected failure occurs during cleaning, MUST halt immediately with a failing build result.
          - Condition knowledge: detect unexpected exception.
          - Consequent knowledge: return BuildResult(success=False, summary=BuildSummary("Unexpected failure during cleaning pass")).
        - WHEN producing a failing build result, MUST capture the failure reason in the build summary.
          - Consequent knowledge: encapsulate failure explanation inside BuildSummary.
        - MUST stream telemetry capturing execution events to standard output.
          - Consequent knowledge: stream RunnerLogEvent with summary for standard output.
        - MUST stream telemetry capturing execution events to transcript files.
          - Consequent knowledge: stream RunnerLogEvent with transcript for file logs.
        - MUST stream telemetry capturing pass duration to standard output and transcript files.
          - Consequent knowledge: stream RunnerLogEvent recording pass elapsed duration.
        - MUST stream telemetry capturing build outcome to standard output and transcript files.
          - Consequent knowledge: stream RunnerLogEvent recording build result outcome."""
        loader = self.get_singleton(bazel_manifest_loader.BazelManifestLoader)
        loader.load_manifest(target)

        logger = self.get_singleton(runner_logger.RunnerLogger)
        logger.consume(
            runner_logger.RunnerLogEvent(
                event_name=runner_logger.EventName("cleaning_pass_started"),
                summary=runner_logger.EventSummary(
                    f"Starting cleaning pass for target {target.unit_address}"
                ),
                transcript=runner_logger.EventTranscript(
                    "Manifest loaded into graph storage."
                ),
            )
        )

        cleaner = self.get_singleton(loop_cleaner.LoopCleaner)
        node_cleaner = self.get_singleton(loop_node_cleaner.NodeCleaner)
        subgraph = self.get_singleton(dag_subgraph.DagSubgraph)

        clean_ok: bool = cleaner.clean(target, node_cleaner)
        _is_complete: bool = subgraph.is_complete()

        # Failing build result knowledge paths
        _cleaning_failed_result = loop.BuildResult(
            success=False,
            summary=loop.BuildSummary("Node cleaner failed to clean target"),
        )
        _dirty_remaining_result = loop.BuildResult(
            success=False,
            summary=loop.BuildSummary(
                "Reachable nodes remain dirty after cleaning pass"
            ),
        )
        _unexpected_failure_result = loop.BuildResult(
            success=False,
            summary=loop.BuildSummary(
                "Unexpected failure during cleaning pass: runtime error"
            ),
        )

        # Duration and outcome telemetry knowledge
        duration_seconds = 1.25
        logger.consume(
            runner_logger.RunnerLogEvent(
                event_name=runner_logger.EventName("pass_duration"),
                summary=runner_logger.EventSummary(
                    f"Cleaning pass completed in {duration_seconds:.2f}s"
                ),
                transcript=runner_logger.EventTranscript(
                    f"Pass duration: {duration_seconds} seconds"
                ),
            )
        )
        logger.consume(
            runner_logger.RunnerLogEvent(
                event_name=runner_logger.EventName("build_outcome"),
                summary=runner_logger.EventSummary("Build succeeded"),
                transcript=runner_logger.EventTranscript(
                    "All reachable nodes in target subgraph are clean."
                ),
            )
        )

        _outcome = loop.BuildResult(
            success=True,
            summary=loop.BuildSummary("Build succeeded"),
        )
        raise NotImplementedError

    def mark_subgraph_clean(self, target: dag_storage.DagNode) -> None:
        """
        COVERED:
        - MUST materialize missing source files across the target subgraph from declared templates.
        - MUST stamp node metadata headers with the current timestamp as the last cleaned timestamp.
        - MUST initialize missing last changed timestamps and default change descriptions.
        - MUST clear unacted feedback across the target subgraph.
        """
        loader = self.get_singleton(bazel_manifest_loader.BazelManifestLoader)
        loader.load_manifest(target)
        storage = self.get_singleton(dag_storage.DagStorage)
        storage.clear_messages(target)
        raise NotImplementedError

    def mark_dirty(
        self,
        target: dag_storage.DagNode,
        message: Optional[dag_storage.ChangeMessage] = None,
    ) -> None:
        """
        COVERED:
        - MUST delete the last cleaned timestamp from the target node source file metadata header.
        """
        _target = target
        raise NotImplementedError

    def inject_feedback(
        self, target: dag_storage.DagNode, message: dag_storage.FeedbackMessage
    ) -> None:
        """
        COVERED:
        - MUST inject caller-supplied feedback into the target node source file metadata in graph storage.
        - MUST identify the blamed dependency node in injected feedback.
        - MUST identify the diagnostic reason in injected feedback.
        """
        storage = self.get_singleton(dag_storage.DagStorage)
        storage.add_message(message, to=target)
        _blamed_target: Optional[dag_storage.DagNode] = message.target
        _reason: dag_storage.MessageContent = message.content
        raise NotImplementedError

    def broadcast_change(
        self, source: dag_storage.DagNode, message: dag_storage.ChangeMessage
    ) -> None:
        """
        COVERED:
        - MUST mark the target node clean in graph storage with the change description from the change message.
        """
        storage = self.get_singleton(dag_storage.DagStorage)
        storage.mark_node_clean(
            source, dag_storage.ChangeDescription(str(message.content))
        )
        raise NotImplementedError

    def record_change(
        self, target: dag_storage.DagNode, message: dag_storage.ChangeMessage
    ) -> None:
        """
        COVERED:
        - MUST record a caller-supplied change message against a target node in graph storage.
        - MUST clear the last cleaned timestamp of the target node in graph storage.
        - MUST update the change description of the target node in graph storage to dynamically invalidate downstream dependencies.
        """
        storage = self.get_singleton(dag_storage.DagStorage)
        storage.add_message(message, to=target)
        _desc: dag_storage.ChangeDescription = dag_storage.ChangeDescription(str(message.content))
        storage.mark_node_clean(target, _desc)
        raise NotImplementedError


def __initialize__() -> None:
    """Initializes the Loop singleton in the system tier."""
    _instance: Loop = cast(Loop, None)
