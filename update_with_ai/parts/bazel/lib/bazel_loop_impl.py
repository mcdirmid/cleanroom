# Requirements specified in bazel_loop_impl.pyi
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


def _format_node(node: dag_storage.Node) -> str:
    if node.role_address:
        return f"{node.unit_address}#{node.role_address}"
    return node.unit_address


class Loop(loop.Loop, Singleton):
    tier = system

    def __init__(self) -> None:
        pass

    def run_cleaning_pass(self, root: dag_storage.Node) -> loop.BuildResult:
        logger = get_singleton(runner_logger.RunnerLogger)
        root_str = _format_node(root)
        # Requirement: Telemetry capturing execution events, cumulative token usage, and pass duration is streamed to standard output and transcript files.
        logger.consume(
            runner_logger.LogEvent(
                event_name="build_pass_start",
                summary=f"Starting cleaning pass for root {root_str}",
                transcript_representation=f"=== Cleaning Pass Started: {root_str} ===",
            )
        )

        manifest_loader = get_singleton(bazel_manifest_loader.BazelManifestLoader)
        storage = get_singleton(dag_storage.DagStorage)
        cleaner = get_singleton(loop_cleaner.LoopCleaner)
        node_cleaner = get_singleton(loop_node_cleaner.NodeCleaner)

        # Requirement: Target labels are resolved against workspace directories or runfiles trees to populate graph storage before cleaning.
        visited: Set[dag_storage.Node] = set()
        queue: list[dag_storage.Node] = [root]
        while queue:
            curr = queue.pop(0)
            if curr in visited:
                continue
            visited.add(curr)
            manifest = manifest_loader.get_manifest(curr)
            if manifest is not None:
                manifest_loader.load_manifest(manifest, cast(Any, storage))
            for dep in storage.get_dependencies(curr):
                if dep.node not in visited:
                    queue.append(dep.node)

        # Requirement: [Loop] The loop executes a cleaning pass over an acyclic subgraph rooted at a target node in graph storage.
        failure_reason: Optional[str] = None
        try:
            cleaner.clean(root, node_cleaner)
            reachable: Set[dag_storage.Node] = set()
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

        if success:
            summary = f"Cleaning pass succeeded for {root_str}"
        else:
            reason_suffix = f": {failure_reason}" if failure_reason else ""
            summary = f"Cleaning pass failed for {root_str}{reason_suffix}"

        # Requirement: Telemetry capturing execution events, cumulative token usage, and pass duration is streamed to standard output and transcript files.
        logger.consume(
            runner_logger.LogEvent(
                event_name="build_pass_end",
                summary=summary,
                transcript_representation=f"=== Cleaning Pass Ended: {summary} ===",
            )
        )
        # Requirement: [Loop] The loop produces a build result upon pass completion.
        return loop.BuildResult(success=success, summary=summary)

    def mark_node_dirty(
        self, target: dag_storage.Node, change: dag_storage.Change
    ) -> None:
        # Requirement: [Loop] The loop marks a target node dirty by injecting a change message into its pending messages.
        storage = get_singleton(dag_storage.DagStorage)
        storage.add_message(change, to=target)

    def inject_node_feedback(
        self, target: dag_storage.Node, feedback: dag_storage.Feedback
    ) -> None:
        # Requirement: [Loop] The loop injects a caller-supplied feedback message into a target node.
        storage = get_singleton(dag_storage.DagStorage)
        storage.add_message(feedback, to=target)

    def broadcast_node_change(
        self, origin: dag_storage.Node, change: dag_storage.Change
    ) -> None:
        # Requirement: [Loop] The loop broadcasts a caller-supplied change message from a node to all of its reverse dependencies.
        storage = get_singleton(dag_storage.DagStorage)
        for dep in storage.get_dependents(origin):
            storage.add_message(change, to=dep)


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        Loop,
        keys=[Loop, loop.Loop],
        tier=system,
    )
