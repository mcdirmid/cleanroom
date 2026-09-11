from typing import Any, Optional, Set, cast
from . import bazel_manifest_loader
from . import bazel_runner
from . import dag_cleaner
from . import dag_node_cleaner
from . import dag_storage
from . import runner_logger
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton

class BazelRunner(bazel_runner.BazelRunner, Singleton):
    tier = "system"

    def __init__(self) -> None:
        pass

    def run_cleaning_pass(self, root: dag_storage.Node) -> bazel_runner.BuildResult:
        # Requirement: [BazelRunner] A bazel runner logs execution events to standard output and transcript files using the runner logger.
        logger = get_singleton(runner_logger.RunnerLogger)
        logger.consume(
            runner_logger.LogEvent(
                event_name="build_pass_start",
                summary=f"Starting cleaning pass for root {root.address}",
                transcript_representation=f"=== Cleaning Pass Started: {root.address} ===",
            )
        )

        manifest_loader = get_singleton(bazel_manifest_loader.BazelManifestLoader)
        storage = get_singleton(dag_storage.DagStorage)
        cleaner = get_singleton(dag_cleaner.DagCleaner)
        node_cleaner = get_singleton(dag_node_cleaner.NodeCleaner)

        # Requirement: The bazel runner resolves target labels and loads workspace target graphs into dag storage using a manifest loader.
        # Requirement: [BazelRunner] A bazel runner resolves target manifests and loads workspace target graphs into dag storage using a manifest loader.
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

        # Requirement: The bazel runner executes cleaning passes in topological order using the dag cleaner and the node cleaner.
        # Requirement: [BazelRunner] A bazel runner cleans dirty nodes in topological order using the dag cleaner and the node cleaner.
        # Requirement: [BazelRunner] A bazel runner executes a cleaning pass over an acyclic subgraph rooted at a target node in dag storage.
        try:
            cleaner.clean(root, node_cleaner)
            success = not storage.is_dirty(root)
        except RuntimeError:
            # Requirement: The bazel runner halts cleaning and reports failure if a node cleaning fails or a cycle is encountered.
            success = False

        if success:
            summary = f"Cleaning pass succeeded for {root.address}"
        else:
            summary = f"Cleaning pass failed for {root.address}"

        # Requirement: [BazelRunner] A bazel runner logs execution events to standard output and transcript files using the runner logger.
        logger.consume(
            runner_logger.LogEvent(
                event_name="build_pass_end",
                summary=summary,
                transcript_representation=f"=== Cleaning Pass Ended: {summary} ===",
            )
        )
        # Requirement: [BazelRunner] A bazel runner produces a build result upon pass completion.
        return bazel_runner.BuildResult(success=success, summary=summary)

    def mark_node_dirty(self, target: dag_storage.Node, message: dag_storage.Change) -> None:
        # Requirement: Marking a node dirty injects a change message with text set to check.
        # Requirement: [BazelRunner] A bazel runner marks a target node dirty by injecting a non-triggering check change message into its pending messages in dag storage.
        storage = get_singleton(dag_storage.DagStorage)
        storage.add_message(message, to=target)

    def inject_node_feedback(self, target: dag_storage.Node, feedback: dag_storage.Feedback) -> None:
        # Requirement: Injecting feedback or broadcasting changes transmits caller-provided message content.
        # Requirement: [BazelRunner] A bazel runner injects a caller-supplied feedback message into a target node.
        storage = get_singleton(dag_storage.DagStorage)
        storage.add_message(feedback, to=target)

    def broadcast_node_change(self, origin: dag_storage.Node, change: dag_storage.Change) -> None:
        # Requirement: Injecting feedback or broadcasting changes transmits caller-provided message content.
        # Requirement: [BazelRunner] A bazel runner broadcasts a caller-supplied change message from a node to all of its reverse dependencies.
        storage = get_singleton(dag_storage.DagStorage)
        for dependent in storage.get_dependents(origin):
            storage.add_message(change, to=dependent)

def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        BazelRunner,
        keys=[BazelRunner, bazel_runner.BazelRunner],
        tier="system",
    )
