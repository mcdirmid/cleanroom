<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-05T04:28:01Z
LAST_CHANGED: 2026-10-04T23:01:55Z
CHANGE: new file
CODE_HASH: e9ec6328489d
-->

# loop interface component

imports: dag_storage

## Purpose

The loop interface component orchestrates complete multi-node build and cleaning passes across workspace nodes to final artifact completion.

Executing multi-stage agent workflows across interdependent graph structures requires evaluating dirty state and coordinating cleaning passes in dependency order. Without a centralized orchestration boundary, callers must manually coordinate node invalidations, state transitions, and change notifications across graph storage. The loop interface component coordinates this end-to-end lifecycle: dispatching cleaning passes across target subgraphs, routing feedback into target nodes, and recording change descriptions on modified nodes to dynamically invalidate downstream dependencies.

**Out of scope:** The loop interface component does not parse build manifests, execute agent turn interactions, or serialize session transcripts; these are handled by other components.

## Types and Behavior

A *cleaning pass* is an execution run that cleans dirty nodes across a target subgraph.

A *build result* is the final outcome of a cleaning pass, reporting overall *success* or failure along with an execution *summary*.

A system's *loop* executes topological build and cleaning passes across workspace nodes.

The loop:

- Executes a cleaning pass over an acyclic subgraph rooted at a target node in graph storage.

- Marks all nodes in an acyclic subgraph clean, materializing missing source files from declared templates, initializing timestamps and default change descriptions, and clearing unacted feedback.

- Marks a target node dirty by removing its last cleaned timestamp from in-band source metadata.

- Injects a caller-supplied feedback message into a target node.

- Records a caller-supplied change message on a target node in graph storage, updating in-band source metadata and dynamically invalidating downstream dependencies.

- Produces a build result upon pass completion.
