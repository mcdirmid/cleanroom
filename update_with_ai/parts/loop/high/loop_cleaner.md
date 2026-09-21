# loop_cleaner interface component

imports: dag_storage, loop_node_cleaner

## Purpose

The loop_cleaner interface component coordinates topological graph execution to ensure dependencies are clean before dependent nodes run.

Executing interconnected tasks in an arbitrary or concurrent sequence risks race conditions, duplicate computations, and stale artifact reads. When an upstream node changes, downstream dependents must be invalidated and updated in dependency order. The loop_cleaner interface component establishes an orchestration boundary that enforces topological execution across subgraphs.

**Out of scope:** The loop_cleaner interface component does not execute single-node tasks, maintain graph topology, or deliver messages; these are handled by other components.

## Types and Behavior

A *loop cleaner* is a system service that coordinates topological graph cleaning across a dag storage.

A loop cleaner can *clean* a target node accepting a *node cleaner*. Cleaning a node cleans dirty nodes in dependency-first topological order, ensuring all dependencies of a node are clean before that node is cleaned. It is assumed that the node roots an acyclic subgraph.

Cleaning dirty nodes halts if the node cleaner communicates that processing cannot continue.

Cleaning concludes when all nodes in the subgraph rooted at the node are clean.
