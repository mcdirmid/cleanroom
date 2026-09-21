from framework import operation, override, singleton_type
import bazel_manifest_loader
import loop
import loop_cleaner
import loop_node_cleaner
import dag_storage
import runner_logger

@singleton_type('system')
class Loop(loop.Loop):
    """
PURPOSE:
Implements bazel workspace execution orchestrating build passes, dirty node resolution, and telemetry logging

GROUNDING_ARGUMENT:
- As a system singleton, Loop coordinates the graph cleaning lifecycle, accessing collaborator singletons in the same system lifecycle tier (bazel_manifest_loader.BazelManifestLoader, loop_cleaner.LoopCleaner, dag_storage.DagStorage, runner_logger.RunnerLogger) and the polymorphic loop_node_cleaner.NodeCleaner, all of which are imported.
"""

    @operation
    @override
    def run_cleaning_pass(self, root: dag_storage.Node) -> loop.BuildResult:
        """
PURPOSE:
Executes a complete topological cleaning pass over the acyclic subgraph rooted at a target node

FRESH_REQUIREMENTS:
- Target labels are resolved against workspace directories or runfiles trees to populate graph storage.
- Cleaning halts immediately and produces a failing build result if node cleaning fails, if any reachable node in the target subgraph remains dirty after cleaning, or if an unexpected failure occurs during cleaning, capturing the failure reason in the build summary.
- Telemetry capturing execution events, pass duration, and build outcome is streamed to standard output and transcript files.

INHERITED_REQUIREMENTS:
- [Loop] The loop executes a cleaning pass over an acyclic subgraph rooted at a target node in graph storage.
- [Loop] The loop produces a build result upon pass completion.

GROUNDING_ARGUMENT:
- Receives root as a parameter, uses imported bazel_manifest_loader to resolve and load workspace targets into dag_storage, invokes imported loop_cleaner to execute topological cleaning passes with the node cleaner, and logs summary duration and build outcome telemetry to runner_logger, with all collaborator singletons residing in the same system lifecycle tier.
"""
        ...

    @operation
    @override
    def mark_node_dirty(self, target: dag_storage.Node, change: dag_storage.Change) -> None:
        """
PURPOSE:
Marks a target node dirty by injecting a change message into its pending messages

INHERITED_REQUIREMENTS:
- [Loop] The loop marks a target node dirty by injecting a change message into its pending messages.

GROUNDING_ARGUMENT:
- Receives target and change parameters directly and injects the change message into target's pending messages in imported dag_storage in the same system lifecycle tier.
"""
        ...

    @operation
    @override
    def inject_node_feedback(self, target: dag_storage.Node, feedback: dag_storage.Feedback) -> None:
        """
PURPOSE:
Injects feedback into a target node message queue, marking it dirty for cleaning

INHERITED_REQUIREMENTS:
- [Loop] The loop injects a caller-supplied feedback message into a target node.

GROUNDING_ARGUMENT:
- Receives target and feedback parameters directly and records the feedback message in imported dag_storage in the same system lifecycle tier to mark the target node dirty.
"""
        ...

    @operation
    @override
    def broadcast_node_change(self, origin: dag_storage.Node, change: dag_storage.Change) -> None:
        """
PURPOSE:
Broadcasts a change message from an origin node to all of its reverse dependencies

INHERITED_REQUIREMENTS:
- [Loop] The loop broadcasts a caller-supplied change message from a node to all of its reverse dependencies.

GROUNDING_ARGUMENT:
- Receives origin and change parameters directly, queries downstream reverse dependents from imported dag_storage, and records the change message on each dependent in the same system lifecycle tier.
"""
        ...
