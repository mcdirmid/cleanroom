<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-09T21:19:01Z
LAST_CHANGED: 2026-10-07T00:00:00Z
CHANGE: new file
CODE_HASH: b64f0f72df8b
-->

# uv_loop_impl implementation component

imports: dag_storage, loop_cleaner, loop_node_cleaner, runner_logger, uv_manifest_loader
implements: loop

## Purpose

The uv_loop_impl implementation component realizes workspace target loading, topological cleaning pass execution, feedback routing, and pass telemetry.

Executing multi-stage agent workflows requires coordinating target loading, dirty state evaluation, and topological cleaning across the graph. Fragmented coordination risks running cleaning passes against unmaterialized dependencies or incomplete session state. The uv_loop_impl implementation component coordinates this end-to-end lifecycle: loading workspace targets into graph storage, dispatching topological cleaning passes using loop cleaner and node cleaner, routing feedback across node boundaries, and capturing execution progress through structured runner logging.

**Out of scope:** The uv_loop_impl implementation component does not parse manifest configuration files, execute individual agent turns, or render user interfaces; these are handled by other components.

**Delegated:** Target manifest loading is delegated to uv_manifest_loader; graph state storage and dirty evaluation are delegated to dag_storage; topological execution is delegated to loop_cleaner; single-node execution is delegated to loop_node_cleaner; execution telemetry and event streaming are delegated to runner_logger.

## Types and Behavior

The loop service coordinates build graph execution and change propagation across workspace targets.

When executing a cleaning pass:

- Target labels are resolved against workspace directories to populate graph storage.

- Cleaning halts immediately and produces a failing build result if node cleaning fails, if any reachable node in the target subgraph remains dirty after cleaning, or if an unexpected failure occurs during cleaning, capturing the failure reason in the build summary.

- Telemetry capturing execution events, pass duration, and build outcome is streamed to standard output and transcript files.

When marking an acyclic subgraph clean:

- Missing source files across the target subgraph are materialized from declared templates or initialized as empty files.

- Node metadata headers are stamped with the current timestamp as the last cleaned timestamp, initializing missing last changed timestamps and default change descriptions, and clearing unacted feedback.

Deleting the last cleaned timestamp from a target node's source file metadata header marks the target node dirty.

When recording feedback:

- Injects caller-supplied feedback into the target node's source file metadata in graph storage, identifying the blamed dependency node and diagnostic reason, and appends the feedback entry to the `.cleanroom.log` file in the directory containing parts.

When recording changes:

- Records a caller-supplied change message against a target node in graph storage, clearing the last cleaned timestamp and updating the change description to dynamically invalidate downstream dependencies, and appends the change message to the `.cleanroom.log` file in the directory containing parts.
