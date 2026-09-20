# bazel_loop_impl implementation component

imports: bazel_manifest_loader, dag_storage, loop, loop_cleaner, loop_node_cleaner, runner_logger
implements: loop

## Purpose

The bazel_loop_impl implementation component realizes workspace target loading, topological cleaning pass execution, feedback routing, and pass telemetry.

Executing multi-stage agent workflows requires coordinating target loading, dirty state evaluation, and topological cleaning across the graph. The bazel_loop_impl implementation component coordinates this end-to-end lifecycle: loading workspace targets into graph storage, dispatching topological cleaning passes using loop cleaner and node cleaner, routing feedback across node boundaries, and capturing execution progress through structured runner logging.

**Out of scope:** The bazel_loop_impl implementation component does not parse manifest JSON files, execute individual agent turns, or render user interfaces; these are handled by other components.

## Types and Behavior

The loop service coordinates build graph execution and change propagation across workspace targets.

When executing a cleaning pass:

- Target labels are resolved against workspace directories or runfiles trees to populate graph storage before cleaning.

- Cleaning halts immediately and produces a failing build result if node cleaning fails, if any reachable node in the target subgraph remains dirty after cleaning, or if an unexpected failure occurs during cleaning, capturing the failure reason in the build summary.

- Telemetry capturing execution events, pass duration, and build outcome is streamed to standard output and transcript files.

> META: "Cycles are only guarded by an assumption and a node visitation limit; cycle detection is never to be turned into a requirement."
