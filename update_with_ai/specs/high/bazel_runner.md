# bazel_runner interface component

imports: dag_storage, dag_cleaner, dag_node_cleaner, runner_logger, bazel_manifest_loader

## Purpose

The bazel_runner interface component orchestrates complete multi-node build and cleaning passes from workspace targets to final artifact completion.

Running multi-stage agent workflows requires coordinating target loading, dirty state evaluation, and topological cleaning across the graph. The bazel_runner interface component coordinates this end-to-end lifecycle: loading workspace targets into graph storage, dispatching topological cleaning passes, routing feedback across node boundaries, and capturing execution progress through structured runner logging.

**Out of scope:** The bazel_runner interface component does not parse manifest JSON files, execute agent turn interactions, or serialize session transcripts; these are handled by other components.

## Types and Behavior

A *cleaning pass* is an execution run that cleans dirty nodes across a target subgraph.

A *build result* is the final outcome of a cleaning pass, reporting overall success or failure along with an execution summary.

The *bazel runner* is a system service that executes topological build and cleaning passes across workspace nodes.

The bazel runner:

- Resolves target manifests and loads workspace target graphs into graph storage.

- Executes a cleaning pass over an acyclic subgraph rooted at a target node.

- Cleans dirty nodes in topological order using the dag cleaner and the node cleaner.

- Marks a target node dirty by injecting a non-triggering check change message into its pending messages.

- Injects a caller-supplied feedback message into a target node.

- Broadcasts a caller-supplied change message from a node to all of its reverse dependencies.

- Logs execution events to standard output and transcript files using the runner logger.

- Produces a build result upon pass completion.
