# loop_cleaner_impl implementation component

imports: dag_storage, dag_subgraph, loop_node_cleaner
implements: loop_cleaner

## Purpose

The loop_cleaner_impl implementation component realizes dependency-first topological graph cleaning and execution iteration bounds using dag subgraph.

Executing complex multi-node workflows requires scheduling tasks in dependency order and re-evaluating dirty status without permitting runaway re-cleaning loops. Orchestrating these steps directly inside node runners creates procedural coupling and duplicates graph traversal algorithms. The loop_cleaner_impl implementation component establishes a clean push loop that consumes topologically ordered ready batches from the dag subgraph and delegates single-node execution to the node cleaner.

**Out of scope:** The loop_cleaner_impl implementation component does not execute single-node tasks, format file aliases, or manage persistent storage; these are handled by other components.

## Types and Behavior

The loop cleaner coordinates dependency-first topological cleaning across a dag storage.

When cleaning a target node:

- Target node scoping sets the target node on the dag subgraph to determine dependency-first topological order.

- Cleaning processes ready batches of dirty nodes in topological order, recording node visits for each cleaned batch, and halts immediately if the node cleaner communicates that processing cannot continue.

- Cleaning concludes when the dag subgraph is complete, indicating all reachable nodes in the target subgraph are clean.
