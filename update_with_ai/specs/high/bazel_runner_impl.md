# bazel_runner_impl implementation component

imports: dag_storage, dag_cleaner, dag_node_cleaner, runner_logger, bazel_manifest_loader
implements: bazel_runner

## Purpose

The bazel_runner_impl implementation component realizes workspace target loading, topological cleaning pass execution, feedback routing, and pass telemetry.

Executing multi-stage agent workflows requires coordinating target loading, dirty state evaluation, and topological cleaning across the graph. The bazel_runner_impl implementation component coordinates this end-to-end lifecycle: loading workspace targets into graph storage, dispatching topological cleaning passes using dag cleaner and node cleaner, routing feedback across node boundaries, and capturing execution progress through structured runner logging.

**Out of scope:** The bazel_runner_impl implementation component does not parse manifest JSON files, execute individual agent turns, or render user interfaces; these are handled by other components.

## Types and Behavior

The bazel runner coordinates build graph execution and change propagation across workspace targets.

When executing a cleaning pass:

- Target labels are resolved against workspace directories or runfiles trees to populate graph storage before cleaning.

- Cleaning halts immediately and produces a failing build result if node cleaning fails or a cycle is detected during topological traversal.

- Telemetry capturing execution events, cumulative token usage, and pass duration is streamed to standard output and transcript files.
