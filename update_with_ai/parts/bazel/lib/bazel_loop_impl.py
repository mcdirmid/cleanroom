# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T20:52:01Z
# LAST_CHANGED: 2026-10-05T05:58:15Z
# CHANGE: Implement change recording and last cleaned timestamp clearing
# CODE_HASH: 852a992b9bb6
# COVERAGE_AUDIT: 2026-10-05T20:52:01Z
# QA_AUDIT: 2026-10-05T20:52:01Z
# --- END CLEANROOM METADATA ---

# Requirements specified in bazel_loop_impl.pyi
import time
from typing import Any, Optional, Set, cast
from . import bazel_manifest_loader
from update_with_ai.parts.loop.lib import loop
from update_with_ai.parts.loop.lib import loop_cleaner
from update_with_ai.parts.loop.lib import loop_node_cleaner
from update_with_ai.parts.dag.lib import dag_storage
from update_with_ai.parts.core.lib import runner_logger
from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    get_singleton,
    system,
)


def _format_node(node: dag_storage.DagNode) -> str:
    if node.role_address:
        return f"{node.unit_address}#{node.role_address}"
    return node.unit_address


class Loop(loop.Loop, Singleton):
    tier = system

    def __init__(self) -> None:
        pass

    def clean_subgraph(self, target: dag_storage.DagNode) -> loop.BuildResult:
        root = target
        start_time = time.time()
        logger = get_singleton(runner_logger.RunnerLogger)
        root_str = _format_node(root)
        # Requirement: Telemetry capturing execution events, pass duration, and build outcome is streamed to standard output and transcript files.
        logger.consume(
            runner_logger.RunnerLogEvent(
                event_name=runner_logger.EventName("build_pass_start"),
                summary=runner_logger.EventSummary(
                    f"Starting cleaning pass for root {root_str}"
                ),
                transcript=runner_logger.EventTranscript(
                    f"=== Cleaning Pass Started: {root_str} ==="
                ),
            )
        )

        manifest_loader = get_singleton(bazel_manifest_loader.BazelManifestLoader)
        storage = get_singleton(dag_storage.DagStorage)
        cleaner = get_singleton(loop_cleaner.LoopCleaner)
        node_cleaner = get_singleton(loop_node_cleaner.NodeCleaner)

        visited: Set[dag_storage.DagNode] = set()
        queue: list[dag_storage.DagNode] = [root]
        while queue:
            curr = queue.pop(0)
            if curr in visited:
                continue
            visited.add(curr)
            manifest_loader.load_manifest(curr)
            for dep in storage.get_dependencies(curr):
                if dep.node not in visited:
                    queue.append(dep.node)

        # Requirement: [Loop] The loop executes a cleaning pass over an acyclic subgraph rooted at a target node in graph storage.
        failure_reason: Optional[str] = None
        try:
            cleaner.clean(root, node_cleaner)
            reachable: Set[dag_storage.DagNode] = set()
            check_queue = [root]
            while check_queue:
                curr_node = check_queue.pop(0)
                if curr_node not in reachable:
                    reachable.add(curr_node)
                    for dep in storage.get_dependencies(curr_node):
                        if dep.node not in reachable:
                            check_queue.append(dep.node)
            # Requirement: Cleaning halts immediately and produces a failing build result if node cleaning fails, if any reachable node in the target subgraph remains dirty after cleaning, or if an unexpected failure occurs during cleaning, capturing the failure reason in the build summary.
            if any(storage.is_dirty(n) for n in reachable | visited):
                success = False
                failure_reason = "reachable nodes remain dirty"
            else:
                success = True
        except RuntimeError as e:
            # Requirement: Cleaning halts immediately and produces a failing build result if node cleaning fails, if any reachable node in the target subgraph remains dirty after cleaning, or if an unexpected failure occurs during cleaning, capturing the failure reason in the build summary.
            success = False
            failure_reason = str(e)

        duration = time.time() - start_time
        if success:
            summary = f"Cleaning pass succeeded for {root_str}"
        else:
            reason_suffix = f": {failure_reason}" if failure_reason else ""
            summary = f"Cleaning pass failed for {root_str}{reason_suffix}"

        telemetry_summary = f"{summary} in {duration:.1f}s"
        logger.consume(
            runner_logger.RunnerLogEvent(
                event_name=runner_logger.EventName("build_pass_end"),
                summary=runner_logger.EventSummary(telemetry_summary),
                transcript=runner_logger.EventTranscript(
                    f"=== Cleaning Pass Ended: {telemetry_summary} ==="
                ),
            )
        )
        return loop.BuildResult(success=success, summary=loop.BuildSummary(summary))

    run_cleaning_pass = clean_subgraph

    def mark_subgraph_clean(self, target: dag_storage.DagNode) -> None:
        import os
        from pathlib import Path

        manifest_loader = get_singleton(bazel_manifest_loader.BazelManifestLoader)
        storage = get_singleton(dag_storage.DagStorage)

        visited: Set[dag_storage.DagNode] = set()
        queue: list[dag_storage.DagNode] = [target]
        while queue:
            curr = queue.pop(0)
            if curr in visited:
                continue
            visited.add(curr)
            manifest_loader.load_manifest(curr)
            for dep in storage.get_dependencies(curr):
                if dep.node not in visited:
                    queue.append(dep.node)

        for node in visited:
            if hasattr(storage, "materialize_template"):
                storage.materialize_template(node)
            if hasattr(storage, "mark_node_clean"):
                storage.mark_node_clean(node)
            else:
                storage.clear_messages(node)

    mark_clean = mark_subgraph_clean

    def mark_dirty(
        self,
        target: dag_storage.DagNode,
        message: Optional[dag_storage.ChangeMessage] = None,
    ) -> None:
        storage = get_singleton(dag_storage.DagStorage)
        if hasattr(storage, "delete_last_cleaned"):
            getattr(storage, "delete_last_cleaned")(target)
        if message is not None:
            storage.add_message(message, to=target)

    mark_node_dirty = mark_dirty

    def inject_feedback(
        self, target: dag_storage.DagNode, message: dag_storage.FeedbackMessage
    ) -> None:
        storage = get_singleton(dag_storage.DagStorage)
        storage.add_message(message, to=target)

    inject_node_feedback = inject_feedback

    def record_change(
        self, target: dag_storage.DagNode, message: dag_storage.ChangeMessage
    ) -> None:
        storage = get_singleton(dag_storage.DagStorage)
        change_text = str(message.content) if message.content else "updated"
        storage.mark_node_clean(target, dag_storage.ChangeDescription(change_text))
        if hasattr(storage, "delete_last_cleaned"):
            getattr(storage, "delete_last_cleaned")(target)
        storage.add_message(message, to=target)

    record_node_change = record_change

    def broadcast_change(
        self, source: dag_storage.DagNode, message: dag_storage.ChangeMessage
    ) -> None:
        self.record_change(source, message)

    broadcast_node_change = broadcast_change


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        Loop,
        keys=[Loop, loop.Loop],
        tier=system,
    )
