# build_runner

imports: dag_storage, dag_cleaner, dag_node_cleaner, runner_logger, manifest_node_loader
types from dag_storage: dag storage, node, message, pending message
types from dag_cleaner: dag cleaner
types from dag_node_cleaner: node cleaner, change message, feedback message
types from runner_logger: runner logger, log event
types from manifest_node_loader: manifest loader

## Purpose

Orchestrates complete multi-node build and cleaning passes from workspace targets to final artifact completion.

Running multi-stage agent workflows requires coordinating target loading, dirty state evaluation, and topological cleaning across the graph. The build runner will be invoked by Starlark rules to coordinate this end-to-end lifecycle: loading workspace targets into graph storage, dispatching topological cleaning passes, routing feedback across node boundaries, and capturing progress through structured runner logging.

## Types

- A *build runner* is an orchestration service that executes topological build and cleaning passes across workspace *nodes*
- A *cleaning pass* is an execution run that cleans dirty *nodes* across a target subgraph
- A *build result* is the final outcome of a *cleaning pass*, reporting overall success or failure

## Behavior

- A *build runner* resolves target manifests and loads workspace target graphs into *dag storage* using a *manifest loader*.
- A *build runner* executes a *cleaning pass* over an acyclic subgraph rooted at a target *node*.
- A *build runner* cleans dirty *nodes* in topological order using a *dag cleaner*.
- A *build runner* marks a target *node* dirty by injecting a non-triggering check *change message*.
- A *build runner* injects a caller-supplied *feedback message* into a target *node*.
- A *build runner* broadcasts a caller-supplied *change message* from a *node* to all of its reverse dependencies.
- A *build runner* logs execution events to standard output and transcript files using a *runner logger*.
- A *build runner* produces a *build result* upon pass completion.
