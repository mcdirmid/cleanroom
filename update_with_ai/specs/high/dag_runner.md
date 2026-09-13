# dag_runner interface component

imports: dag_storage

## Purpose

The dag_runner interface component orchestrates complete multi-node build and cleaning passes across workspace nodes to final artifact completion.

Executing multi-stage agent workflows across interdependent graph structures requires evaluating dirty state and coordinating cleaning passes in dependency order. Without a centralized orchestration boundary, callers must manually coordinate node invalidations, state transitions, and change notifications across graph storage. The dag_runner interface component coordinates this end-to-end lifecycle: dispatching cleaning passes across target subgraphs, routing feedback into target nodes, and broadcasting change messages to reverse dependencies.

**Out of scope:** The dag_runner interface component does not parse build manifests, execute agent turn interactions, or serialize session transcripts; these are handled by other components.

## Types and Behavior

A *cleaning pass* is an execution run that cleans dirty nodes across a target subgraph.

A *build result* is the final outcome of a cleaning pass, reporting overall success or failure along with an execution summary.

The *dag runner* is a system service that executes topological build and cleaning passes across workspace nodes.

The dag runner:

- Executes a cleaning pass over an acyclic subgraph rooted at a target node in graph storage.

- Marks a target node dirty by injecting a change message into its pending messages.

- Injects a caller-supplied feedback message into a target node.

- Broadcasts a caller-supplied change message from a node to all of its reverse dependencies.

- Produces a build result upon pass completion.
