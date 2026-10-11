<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-11T22:09:02Z
LAST_CHANGED: 2026-10-11T02:20:00Z
CHANGE: Name the lifecycles between the loop cleaner and its collaborators and state scoping declaratively
CODE_HASH: b56263845f3f
SPEC_QA_AUDIT: 2026-10-11T22:09:02Z
-->

# loop_cleaner_impl implementation component

imports: dag_storage, dag_subgraph, loop_node_cleaner
implements: loop_cleaner

## Purpose

The loop_cleaner_impl implementation component realizes dependency-first topological graph cleaning and execution iteration bounds using dag subgraph.

Executing complex multi-node workflows requires scheduling tasks in dependency order and re-evaluating dirty status without permitting runaway re-cleaning loops. Orchestrating these steps directly inside node runners creates procedural coupling and duplicates graph traversal algorithms. The loop_cleaner_impl implementation component establishes a clean push loop that consumes topologically ordered ready batches from the dag subgraph and delegates single-node execution to the node cleaner.

**Out of scope:** The loop_cleaner_impl implementation component does not execute single-node tasks, format file aliases, or manage persistent storage; these are handled by other components.

**Delegated:** Node execution is delegated to loop_node_cleaner; subgraph batching and topological ordering are delegated to dag_subgraph.

## Types and Behavior

Cleaning a target node through the loop cleaner scopes an active subgraph by setting the target node on the dag subgraph, which determines the dependency-first topological order of the reachable nodes.

Cleaning then processes ready batches of dirty nodes in topological order, records node visits for each cleaned batch, and halts immediately when the node cleaner communicates that processing cannot continue.

Cleaning concludes when the dag subgraph reports that the target subgraph is complete, meaning every reachable node in the target subgraph is clean in dag storage.
