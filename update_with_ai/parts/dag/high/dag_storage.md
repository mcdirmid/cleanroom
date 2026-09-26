# dag_storage interface component

## Purpose

The dag_storage interface component coordinates incremental workflow execution and inter-task diagnostic communication across multi-step agent runs.

Multi-step agent workflows require coordinated incremental execution to avoid redundant re-computation and prevent stale task outputs. As tasks evolve, dependent stages must understand why upstream changes necessitate re-execution, and downstream stages must communicate diagnostic issues back to their prerequisites. The dag_storage interface component provides a dedicated graph coordination boundary that isolates lifecycle tracking and inter-node communication state from the operational mechanics of individual task execution.

**Out of scope:** The dag_storage interface component does not determine which dependencies are silent, dispatch change notifications, interpret message semantics, or execute node cleaning; these are handled by other components.

## Types and Behavior

A *unit* is an end-artifact that is being worked on, while a *role* describes a phase of work being done to an artifact.

A *dag node* identifies a discrete unit of work in the graph, having a unit address and a role address.

A system's *dag storage* stores node graph structure, status, and messages.

A dag storage provides access to a node's *dag dependencies* that refer to its direct upstream nodes in the graph, identifying whether a dependency is *silent* to preclude change message propagation from that dependency.

A dag storage can register a node as a dependent to all of its non-silent dependencies, can access dependents registered to a node, and can clear the dependents registered to a node.

A *dag message* is text content explaining to the agent why a node requires cleaning, and is either a *change message* informing of changes made to upstream dependencies, or a *feedback message* blaming a specific dependency target node for defects detected by downstream dependents.

A dag storage can add messages to, access messages for, and clear messages from a node. A dag storage exposes whether a node is dirty, meaning it requires cleaning. A node is considered dirty if it has messages.
