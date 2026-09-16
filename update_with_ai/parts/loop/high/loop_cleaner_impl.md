# loop_cleaner_impl implementation component

imports: dag_storage, dag_subgraph, loop_node_cleaner
implements: loop_cleaner

## Purpose

The loop_cleaner_impl implementation component realizes dependency-first topological graph cleaning and execution iteration bounds using dag subgraph.

Executing complex multi-node workflows requires scheduling tasks in dependency order and re-evaluating dirty status without permitting runaway re-cleaning loops. Orchestrating these steps directly inside node runners creates procedural coupling and duplicates graph traversal algorithms. The loop_cleaner_impl implementation component establishes a clean push loop that consumes topologically ordered ready batches from the dag subgraph and delegates single-node execution to the node cleaner.

**Out of scope:** The loop_cleaner_impl implementation component does not execute single-node tasks, format file aliases, or manage persistent storage; these are handled by other components.

## Types and Behavior

The loop cleaner coordinates dependency-first topological cleaning across a dag storage using a node cleaner.

When cleaning a target node:

- Target node initialization sets the target on the dag subgraph to collect reachable nodes and determine their topological order.

- Cleaning loops while the dag subgraph is not complete, obtaining the next ready batch of dirty nodes from the dag subgraph, recording the visit on the dag subgraph, and delegating cleaning to the node cleaner.

- If the node cleaner communicates that processing cannot continue, cleaning halts immediately.

- Cleaning concludes when the dag subgraph is complete, indicating all reachable nodes in the target subgraph are clean.
