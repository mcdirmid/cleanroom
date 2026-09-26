from typing import Self
from framework import operation, override, singleton_type
import bazel_manifest_loader
import loop
import loop_cleaner
import loop_node_cleaner
import dag_storage
import runner_logger


@singleton_type('system')
class Loop(loop.Loop):
    """Implements bazel workspace execution orchestrating build passes, dirty node resolution, and telemetry logging.

    GROUNDING_ARGUMENT:
    - As a system singleton, Loop coordinates the graph cleaning lifecycle, accessing collaborator singletons in the same system lifecycle tier (bazel_manifest_loader.BazelManifestLoader, loop_cleaner.LoopCleaner, dag_storage.DagStorage, runner_logger.RunnerLogger) and the polymorphic loop_node_cleaner.NodeCleaner, all of which are imported.
    """

    @operation
    @override
    def run_cleaning_pass(self, root: dag_storage.DagNode) -> loop.BuildResult:
        """Executes a complete topological cleaning pass over the acyclic subgraph rooted at a target node.

        REQUIREMENTS:
        - Target labels are resolved against workspace directories or runfiles trees to populate graph storage.
        - Cleaning halts immediately and produces a failing build result if node cleaning fails, if any reachable node in the target subgraph remains dirty after cleaning, or if an unexpected failure occurs during cleaning, capturing the failure reason in the build summary.
        - Telemetry capturing execution events, pass duration, and build outcome is streamed to standard output and transcript files.

        GROUNDING_PROVISIONS:
        - action("run_cleaning_pass", loop.BuildResult): Runs topological cleaning pass.

        GROUNDING_ARGUMENT:
        - action("run_cleaning_pass", Self) :- action("get_manifest", bazel_manifest_loader.BazelManifestLoader), action("load_manifest", bazel_manifest_loader.BazelManifestLoader), action("clean", loop_cleaner.LoopCleaner), action("consume_log_event", runner_logger.RunnerLogger).
        """
        ...

    @operation
    @override
    def mark_node_dirty(self, target: dag_storage.DagNode, change: dag_storage.ChangeMessage) -> None:
        """Marks a target node dirty by injecting a change message into its pending messages.

        GROUNDING_PROVISIONS:
        - action("mark_node_dirty", None): Marks node dirty.

        GROUNDING_ARGUMENT:
        - action("mark_node_dirty", Self) :- action("add_message", dag_storage.DagStorage).
        """
        ...

    @operation
    @override
    def inject_node_feedback(self, target: dag_storage.DagNode, feedback: dag_storage.FeedbackMessage) -> None:
        """Injects feedback into a target node message queue, marking it dirty for cleaning.

        GROUNDING_PROVISIONS:
        - action("inject_node_feedback", None): Injects feedback into target node.

        GROUNDING_ARGUMENT:
        - action("inject_node_feedback", Self) :- action("add_message", dag_storage.DagStorage).
        """
        ...

    @operation
    @override
    def broadcast_node_change(self, origin: dag_storage.DagNode, change: dag_storage.ChangeMessage) -> None:
        """Broadcasts a change message from an origin node to all of its reverse dependencies.

        GROUNDING_PROVISIONS:
        - action("broadcast_node_change", None): Broadcasts change to downstream reverse dependents.

        GROUNDING_ARGUMENT:
        - action("broadcast_node_change", Self) :- knows("downstream_dependents", dag_storage.DagStorage), action("add_message", dag_storage.DagStorage).
        """
        ...
