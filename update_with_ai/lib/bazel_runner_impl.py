from typing import Optional
from . import bazel_manifest_loader
from . import bazel_runner
from . import dag_cleaner
from . import dag_node_cleaner
from . import dag_storage
from . import runner_logger
from .lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton

class BazelRunner(bazel_runner.BazelRunner, Singleton):
    tier = "system"

    def __init__(self) -> None:
        pass

    def run_cleaning_pass(self, root: dag_storage.Node) -> bazel_runner.BuildResult:
        # Requirement: Logs cleaning pass initiation to runner logger
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

        # Requirement: Pre-loads root target manifest definitions when available
        manifest = manifest_loader.get_manifest(root)
        if manifest is not None:
            manifest_loader.load_manifest(manifest, storage)  # type: ignore

        # Requirement: Executes dag cleaner with node cleaner to resolve dirty states
        try:
            cleaner.clean(root, node_cleaner)
            success = not storage.is_dirty(root)
        except RuntimeError:
            success = False

        if success:
            summary = f"Cleaning pass succeeded for {root.address}"
        else:
            summary = f"Cleaning pass failed for {root.address}"

        # Requirement: Logs cleaning pass completion to runner logger
        logger.consume(
            runner_logger.LogEvent(
                event_name="build_pass_end",
                summary=summary,
                transcript_representation=f"=== Cleaning Pass Ended: {summary} ===",
            )
        )
        # Requirement: Returns build result with success indicator and summary
        return bazel_runner.BuildResult(success=success, summary=summary)

    def mark_node_dirty(self, target: dag_storage.Node, message: dag_storage.Change) -> None:
        # Requirement: Marks a target node dirty by recording an incoming change message
        storage = get_singleton(dag_storage.DagStorage)
        storage.add_message(message, to=target)

    def inject_node_feedback(self, target: dag_storage.Node, feedback: dag_storage.Feedback) -> None:
        # Requirement: Injects a feedback message directed to a dependency node
        storage = get_singleton(dag_storage.DagStorage)
        storage.add_message(feedback, to=target)

    def broadcast_node_change(self, origin: dag_storage.Node, change: dag_storage.Change) -> None:
        # Requirement: Broadcasts change notification messages to all downstream dependents
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
