# dag_subgraph interface component

imports: dag_storage

## Purpose

The dag_subgraph interface component provides an active subgraph view over graph storage to query topological order, evaluate completion status, and batch ready dirty nodes for execution schedulers.

Coordinating multi-node agent workflows requires inspecting graph progress, identifying independent tasks that can be scheduled concurrently, and isolating reachable dependencies from unrelated workspace targets. Direct queries against unstructured graph storage force orchestrators to re-implement graph traversal algorithms and duplicate dependency validation, risking race conditions and inconsistent execution schedules. The dag_subgraph interface component establishes a query boundary over graph storage that maintains an active target subgraph, isolates reachable dependencies, and delivers topologically sorted, ready-to-clean node batches to execution runners.

**Out of scope:** The dag_subgraph interface component does not clean individual nodes, manage message delivery, or execute agent turn loops; these are handled by other components.

## Types and Behavior

The *dag subgraph* is a system service that models an active execution subgraph rooted at a target node in dag storage.

The dag subgraph:

- Can *set target* to a target node in dag storage, collecting reachable dependency nodes from the target node in dag storage and computing their dependency-first topological order.

- Reports whether the target subgraph is *complete*, which holds if, but only if, all reachable nodes in the target subgraph are clean in dag storage.

- Provides the *next ready batch* of dirty nodes to clean, selecting uncleaned dirty nodes prioritized by role tier precedence (upstream roles before downstream roles) whose dependencies in the target subgraph are clean in dag storage or present in the same ready batch, grouped by role address up to a maximum batch size.

- Can *record visit* for a batch of nodes being cleaned, incrementing visit counts for each node in the batch and enforcing execution iteration limits.
