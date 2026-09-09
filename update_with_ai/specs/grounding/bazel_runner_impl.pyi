from framework import operation, override, singleton_type
import bazel_manifest_loader
import bazel_runner
import dag_cleaner
import dag_node_cleaner
import dag_storage
import runner_logger

@singleton_type('system')
class BazelRunner(bazel_runner.BazelRunner):
    """
PURPOSE:
Implements bazel runner orchestrating build passes, dirty node resolution, and telemetry logging

FRESH_REQUIREMENTS:
- Injecting feedback or broadcasting changes transmits caller-provided message content.

GROUNDING_ARGUMENT:
- As a system singleton, BazelRunner coordinates the graph cleaning lifecycle, accessing collaborator singletons in the same system lifecycle tier (bazel_manifest_loader.BazelManifestLoader, dag_cleaner.DagCleaner, dag_storage.DagStorage, runner_logger.RunnerLogger) and the polymorphic dag_node_cleaner.NodeCleaner, all of which are imported.
"""

    @operation
    @override
    def run_cleaning_pass(self, root: dag_storage.Node) -> bazel_runner.BuildResult:
        """
PURPOSE:
Executes a complete topological cleaning pass over the acyclic subgraph rooted at a target node

FRESH_REQUIREMENTS:
- The bazel runner resolves target labels and loads workspace target graphs into dag storage using a manifest loader.
- The bazel runner executes cleaning passes in topological order using the dag cleaner and the node cleaner.
- The bazel runner halts cleaning and reports failure if a node cleaning fails or a cycle is encountered.
- When an agent session concludes, the bazel runner logs cumulative token usage and pass duration.

INHERITED_REQUIREMENTS:
- [BazelRunner] A bazel runner resolves target manifests and loads workspace target graphs into dag storage using a manifest loader.
- [BazelRunner] A bazel runner executes a cleaning pass over an acyclic subgraph rooted at a target node in dag storage.
- [BazelRunner] A bazel runner cleans dirty nodes in topological order using the dag cleaner and the node cleaner.
- [BazelRunner] A bazel runner logs execution events to standard output and transcript files using the runner logger.
- [BazelRunner] A bazel runner produces a build result upon pass completion.

GROUNDING_ARGUMENT:
- Receives root as a parameter, uses imported bazel_manifest_loader to resolve and load workspace targets into dag_storage, invokes imported dag_cleaner to execute topological cleaning passes with the node cleaner, and logs summary duration and token telemetry to runner_logger, with all collaborator singletons residing in the same system lifecycle tier.
"""
        ...

    @operation
    @override
    def mark_node_dirty(self, target: dag_storage.Node, message: dag_storage.Change) -> None:
        """
PURPOSE:
Marks a target node dirty by injecting a check change message into its pending messages

FRESH_REQUIREMENTS:
- Marking a node dirty injects a change message with text set to check.

INHERITED_REQUIREMENTS:
- [BazelRunner] A bazel runner marks a target node dirty by injecting a non-triggering check change message into its pending messages in dag storage.

GROUNDING_ARGUMENT:
- Receives target and message parameters directly and injects the check change message into target's pending messages in imported dag_storage in the same system lifecycle tier.
"""
        ...

    @operation
    @override
    def inject_node_feedback(self, target: dag_storage.Node, feedback: dag_storage.Feedback) -> None:
        """
PURPOSE:
Injects feedback into a target node message queue, marking it dirty for cleaning

INHERITED_REQUIREMENTS:
- [BazelRunner] A bazel runner injects a caller-supplied feedback message into a target node.

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
- [BazelRunner] A bazel runner broadcasts a caller-supplied change message from a node to all of its reverse dependencies.

GROUNDING_ARGUMENT:
- Receives origin and change parameters directly, queries downstream reverse dependents from imported dag_storage, and records the change message on each dependent in the same system lifecycle tier.
"""
        ...
