# dag_storage interface component

## Purpose

The dag_storage interface component coordinates incremental workflow execution and inter-task diagnostic communication across multi-step agent runs.

Multi-step agent workflows require coordinated incremental execution to avoid redundant re-computation and prevent stale task outputs. As tasks evolve, dependent stages must understand why upstream changes necessitate re-execution, and downstream stages must communicate diagnostic issues back to their prerequisites. The dag_storage interface component provides a dedicated graph coordination boundary that isolates lifecycle tracking and inter-node communication state from the operational mechanics of individual task execution.

**Out of scope:** The dag_storage interface component does not determine which dependencies are silent, dispatch change notifications, interpret message semantics, or execute node cleaning; these are handled by other components.

## Types and Behavior

A *node* identifies a discrete unit of work in the graph. A *dag storage* is a system service that maintains node state, including its graph structure and change propagation. A node in a dag storage has:

- *Dependencies* that refer to the node's upstream nodes in the graph. A dependency can be *silent* to indicate that the dependent node does not depend on the dependency's content and so does not need to receive change messages about the dependency.

- *Dependents* that refer to downstream nodes depending on it. A node can be *registered* as a dependent to all of its non-silent dependencies so that it can be notified when dependencies change. The dependents of a node can be *cleared* to avoid stale dependent relationships.

- *Messages* explaining why the node requires cleaning. A message can either indicate *change*, which informs of modifications made to upstream dependencies, or *feedback*, which informs of issues detected by downstream dependents. A node is *dirty*, meaning it needs to be cleaned, if, but not only if, it has messages. Messages can be *added* to a node, to inform on why it needs to be cleaned, as well as *cleared*, to inform that it no longer needs to be cleaned.