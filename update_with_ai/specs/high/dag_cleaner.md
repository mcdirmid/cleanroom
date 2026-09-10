# dag_cleaner interface component

imports: dag_storage, dag_node_cleaner

## Purpose

The dag_cleaner interface component coordinates topological graph execution to ensure dependencies are clean before dependent nodes run.

Executing interconnected tasks in an arbitrary or concurrent sequence risks race conditions, duplicate computations, and stale artifact reads. When an upstream node changes, downstream dependents must be invalidated and updated in dependency order. The dag_cleaner interface component establishes an orchestration boundary that enforces topological execution across subgraphs.

**Out of scope:** The dag_cleaner interface component does not execute single-node tasks, maintain graph topology, or deliver messages; these are handled by other components.

## Types and Behavior

A *dag cleaner* is a system service that coordinates topological graph cleaning across a dag storage using a node cleaner.

A dag cleaner can *clean* a target node using a node cleaner. Cleaning a node cleans dirty nodes in dependency-first topological order, ensuring all dependencies of a node are clean before that node is cleaned. It is assumed that the node roots an acyclic subgraph in dag storage.

When cleaning a dirty node using the node cleaner, cleaning delegates to the node cleaner. If the node cleaner communicates that processing cannot continue, cleaning halts.

Cleaning concludes when all nodes in the subgraph rooted at the node are clean.
