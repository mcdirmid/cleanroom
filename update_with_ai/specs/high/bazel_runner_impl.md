# bazel_runner_impl implementation component

imports: dag_storage, dag_cleaner, dag_node_cleaner, runner_logger, bazel_manifest_loader
implements: bazel_runner

## Purpose

The bazel_runner_impl implementation component realizes workspace target loading, topological cleaning pass execution, feedback routing, and pass telemetry.

Executing multi-stage agent workflows requires coordinating target loading, dirty state evaluation, and topological cleaning across the graph. The bazel_runner_impl implementation component coordinates this end-to-end lifecycle: loading workspace targets into graph storage, dispatching topological cleaning passes using dag cleaner and node cleaner, routing feedback across node boundaries, and capturing execution progress through structured runner logging.

**Out of scope:** The bazel_runner_impl implementation component does not parse manifest JSON files, execute individual agent turns, or render user interfaces; these are handled by other components.

## Types and Behavior

The bazel runner coordinates build graph execution and change propagation across workspace targets. The bazel runner:

- Resolves target labels and loads workspace target graphs into dag storage from dag storage using the bazel manifest loader from bazel manifest loader.

- Executes cleaning passes in topological order using the dag cleaner from dag cleaner and the node cleaner from dag node cleaner.

- Marks a node dirty by injecting a change message with text set to check into its pending messages in dag storage.

- Injects caller-provided feedback messages into a target node's message queue in dag storage, or broadcasts caller-provided change messages to all of a node's reverse dependencies.

- Halts cleaning and produces a failing build result if node cleaning fails or a cycle is encountered.

- Logs execution events, cumulative token usage, and pass duration to standard output and transcript files using the runner logger from runner logger.
