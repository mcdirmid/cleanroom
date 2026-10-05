<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-05T20:52:01Z
LAST_CHANGED: 2026-10-05T04:52:49Z
CHANGE: Remove forbidden optional keyword from change description condition
CODE_HASH: f67cefe8fd65
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

A *dag message* is text content explaining to the agent why a node requires cleaning, and is either a *change message* informing of changes made to upstream dependencies, or a *feedback message* blaming a specific dependency target node for defects detected by downstream dependents.

A dag storage provides access to messages for a node, can record feedback messages blaming dependency target nodes, can record change messages marking a target node dirty, can *materialize a template* for a node when its source artifact is missing on disk, can *mark a node clean* in graph storage, and exposes whether a node is *dirty*, meaning it requires cleaning.

A node is considered dirty if its source artifact is missing on disk, if its in-band metadata is missing, invalid, or uncleaned, if it has unacted feedback messages, or if any non-silent dependency was changed after the node was last cleaned.

Recording a change message against a target node marks it dirty by updating its in-band metadata with the change description and clearing its last cleaned status.

Materializing a template for a node writes initial template content to disk if its source artifact is missing on disk, preserving existing files without overwriting.

Marking a node clean clears messages for the node and updates in-band metadata with a clean timestamp. When a change description is provided for a node with a source artifact, marking the node clean updates its last changed timestamp and change description in its in-band metadata, and clears unacted feedback. When marking an auditor node clean, audit metadata is stamped across all of its feedback dependencies.
