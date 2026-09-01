# dag_cleaner

imports: dag_storage, dag_node_cleaner
types from dag_storage: dag storage, node, pending message
types from dag_node_cleaner: node cleaner, change message, feedback message

## Purpose

Orchestrates topological subgraph cleaning across a directed acyclic graph, ensuring dependencies are clean before dependents run.

Cleaning interconnected build nodes in arbitrary order causes race conditions, duplicate executions, and stale reads. DAG cleaner coordinates cleaning across acyclic subgraphs in strict topological order, broadcasting change messages downstream and routing feedback messages upstream.

## Types

- A *dag cleaner* is an orchestration service that cleans subgraphs in a *dag storage* using a *node cleaner*

## Behavior

- A *dag cleaner* can clean an acyclic subgraph rooted at a target *node* in a *dag storage*.
- A *dag cleaner* cleans dirty *nodes* in topological order, ensuring dependencies are clean before dependent *nodes* execute.
- A *dag cleaner* routes *change messages* produced by a cleaned *node* to its reverse dependencies.
- A *dag cleaner* routes *feedback messages* produced by a cleaned *node* to its dependencies.
