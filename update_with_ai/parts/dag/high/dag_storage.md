# dag_storage interface component

## Purpose

The dag_storage interface component coordinates incremental workflow execution and inter-task diagnostic communication across multi-step agent runs.

Multi-step agent workflows require coordinated incremental execution to avoid redundant re-computation and prevent stale task outputs. As tasks evolve, dependent stages must understand why upstream changes necessitate re-execution, and downstream stages must communicate diagnostic issues back to their prerequisites. The dag_storage interface component provides a dedicated graph coordination boundary that isolates lifecycle tracking and inter-node communication state from the operational mechanics of individual task execution.

**Out of scope:** The dag_storage interface component does not determine which dependencies are silent, dispatch change notifications, interpret message semantics, or execute node cleaning; these are handled by other components.

## Types and Behavior

A *node* identifies a discrete unit of work in the graph, having a *unit address* and a *role address*.

A *message* explains why a node requires cleaning, carrying text *content*. A message is either:

- A *change* message, informing of modifications made to upstream dependencies.

- A *feedback* message, informing of defects detected by downstream dependents and addressed to a specific dependency node.

A node is *dirty*, meaning it requires cleaning, if, but not only if, it has messages.

A *dag storage* is a system service that stores graph structure, node status, and message propagation across nodes.

A dag storage:

- Stores node *dependencies* referring to upstream nodes in the graph, identifying whether a dependency is *silent* to preclude change propagation from that dependency.

- Stores node *dependents* referring to downstream nodes depending on that node.

- Can *register* a node as a dependent to all of its non-silent dependencies.

- Can *clear* the dependents of a node.

- Exposes whether a node is dirty.

- Can *add* messages to a node.

- Can *clear* messages from a node.
