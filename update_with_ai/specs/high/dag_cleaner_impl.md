# dag_cleaner_impl implementation component

imports: dag_storage, dag_node_cleaner
implements: dag_cleaner

## Purpose

The dag_cleaner_impl implementation component realizes iterative topological graph cleaning with execution limits.

Unbounded feedback loops between dependent tasks can cause graph cleaners to run indefinitely, exhausting memory and stalling execution pipelines. The dag_cleaner_impl implementation component provides deterministic topological sorting, iteration-bounded re-evaluation, and robust failure handling, ensuring graph traversal terminates predictably even when tasks oscillate.

**Out of scope:** The dag_cleaner_impl implementation component does not execute node tasks, persist graph changes to disk, or format diagnostic messages; these are handled by other components.

## Types and Behavior

A dag cleaner has an *execution limit* hardcoded to 500 that bounds the maximum times any node can be visited to check whether it is dirty.

A dag cleaner cleans a target node by collecting all reachable dependencies from the node and executing them in dependency-first topological order.

In each cleaning iteration, the dag cleaner visits reachable nodes in topological order. Visiting a node checks whether the node is dirty, not whether it is cleaned. A node is cleaned only if it is dirty and all of its dependencies are clean. When cleaning a dirty node:

- The node cleaner is invoked to clean the node.

- If the node cleaner communicates that processing cannot continue, cleaning halts.

Cleaning is bounded to prevent infinite loops. If visiting any node exceeds the execution limit, the dag cleaner halts with an unexpected failure. Cleaning succeeds when all reachable nodes in the subgraph are clean.
