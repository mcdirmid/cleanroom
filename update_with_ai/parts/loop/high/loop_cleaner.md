<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-12T18:21:03Z
LAST_CHANGED: 2026-10-11T02:20:00Z
CHANGE: Consolidate the acyclicity assumption and state halting and completion as declarative invariants
CODE_HASH: c6d224f360b8
SPEC_QA_AUDIT: 2026-10-12T18:21:03Z
-->

# loop_cleaner interface component

imports: dag_storage, loop_node_cleaner

## Purpose

The loop_cleaner interface component coordinates topological graph execution to ensure dependencies are clean before dependent nodes run.

Executing interconnected tasks in an arbitrary or concurrent sequence risks race conditions, duplicate computations, and stale artifact reads. When an upstream node changes, downstream dependents must be invalidated and updated in dependency order. The loop_cleaner interface component establishes an orchestration boundary that enforces topological execution across subgraphs.

**Out of scope:** The loop_cleaner interface component does not execute single-node tasks, maintain graph topology, check whether subgraphs are acyclic, or deliver messages; these are handled by other components.

## Types and Behavior

A system's *loop cleaner* coordinates topological graph cleaning across a dag storage.

A loop cleaner can clean a target node using a supplied node cleaner, cleaning dirty nodes in dependency-first topological order so that every dependency of a node is clean before the node is cleaned.

A caller guarantees that the target node roots an acyclic subgraph, because checking whether a subgraph is acyclic is out of scope.

Cleaning dirty nodes halts when the node cleaner communicates that processing cannot continue, and concludes once every node in the subgraph rooted at the target node is clean.
