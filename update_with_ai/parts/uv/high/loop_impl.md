<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:47Z
LAST_CHANGED: 2026-10-07T00:00:00Z
CHANGE: new file
CODE_HASH: 04904f08a22e
SPEC_QA_AUDIT: 2026-10-15T17:42:47Z
-->

# loop_impl implementation component

imports: cleanroom_files_ext, dag_storage, cleaner, node_cleaner, logger, manifest_loader
implements: loop

## Purpose

The loop_impl implementation component realizes workspace target loading, topological cleaning pass execution, feedback routing, and pass telemetry.

Executing multi-stage agent workflows requires coordinating target loading, dirty state evaluation, and topological cleaning across the graph. Fragmented coordination risks running cleaning passes against unmaterialized dependencies or incomplete session state. The loop_impl implementation component coordinates this end-to-end lifecycle: loading workspace targets into graph storage, dispatching topological cleaning passes using loop cleaner and node cleaner, routing feedback across node boundaries, and capturing execution progress through structured runner logging.

**Out of scope:** The loop_impl implementation component does not parse manifest configuration files, execute individual agent turns, or render user interfaces; these are handled by other components.

**Delegated:** Cleanroom log file naming is delegated to cleanroom_files_ext; target manifest loading is delegated to uv_manifest_loader; graph state storage and dirty evaluation are delegated to dag_storage; topological execution is delegated to loop_cleaner; single-node execution is delegated to loop_node_cleaner; execution telemetry and event streaming are delegated to logger.

## Types and Behavior

The loop service coordinates build graph execution and change propagation across workspace targets. The loop service resolves target labels against workspace directories to populate graph storage.

When executing a cleaning pass:

- Cleaning halts immediately and produces a failing build result when node cleaning fails, when any reachable node in the target subgraph remains dirty after cleaning, or when an unexpected failure occurs during cleaning, capturing the failure reason in the build summary.

- Telemetry capturing execution events, pass duration, and the build outcome is streamed to standard output and the transcript files.

When marking an acyclic subgraph clean:

- Missing source files across the target subgraph are materialized from declared templates or initialized as empty files.

- Node metadata headers are stamped with the current timestamp as the last cleaned timestamp, initializing a missing last changed timestamp and a default change summary, and clearing unacted feedback.

Deleting the last cleaned timestamp from a target node's source file metadata header marks the target node dirty.

When recording feedback:

- Injects caller-supplied feedback into the target node's source file metadata in graph storage, identifying the blamed dependency node and the diagnostic reason, and appends the feedback entry to the cleanroom log file in the directory containing the parts.

When recording changes:

- Records a caller-supplied change message against a target node in graph storage, clearing the last cleaned timestamp and updating the change summary to dynamically invalidate downstream dependencies, and appends the change message to the cleanroom log file in the directory containing the parts.
