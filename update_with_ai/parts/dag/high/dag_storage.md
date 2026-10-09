<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-09T21:19:01Z
LAST_CHANGED: 2026-10-08T00:30:58Z
CHANGE: Update dag_storage operations: mark_node_dirty, mark_subgraph_clean, add_feedback_message, and refined change message semantics
CODE_HASH: 0239f4adf890
-->

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

A *dag message* is text content explaining to the agent why a node requires cleaning, and is either a *change message* informing how an upstream dependency changed, or a *feedback message* blaming a specific dependency target node for defects detected by downstream dependents.

A dag storage provides access to messages for a node, can *add a feedback message* blaming a dependency target node, can *materialize a template* for a node when its source artifact is missing on disk, can *mark a node clean* in graph storage, can *mark a node dirty*, can *mark a subgraph clean*, and exposes whether a node is *dirty*, meaning it requires cleaning.

A node evaluates as dirty when its source artifact is missing on disk, when its in-band metadata is missing, invalid, or uncleaned, when it has been marked dirty with a dirty tag, when it contains unacted feedback messages, or when any non-silent dependency was changed after the node was last cleaned.

Change messages communicate how upstream dependencies changed to their downstream dependents rather than marking nodes dirty directly.

Adding a feedback message blaming a dependency target node records the critique in the target node's in-band metadata as unacted feedback.

Marking a node clean clears messages for the node and updates in-band metadata with a clean timestamp. When a change message is provided for a node with a source artifact, marking the node clean updates its change timestamp and change summary in its in-band metadata with the change message content, and clears unacted feedback and dirty tags. When marking an auditor node clean, audit metadata is stamped across all of its feedback dependencies.

Marking a node dirty removes its clean status and records an optional dirty reason in its in-band metadata header.

Marking a subgraph clean materializes missing templates and marks the target node and all reachable dependencies in its subgraph clean in graph storage.

Materializing a template for a node writes initial template content to disk if its source artifact is missing on disk, preserving existing files without overwriting.
