<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-11T01:51:09Z
CHANGE: Complete the operation inventory, scope out low-level operations correctly, and bind the dirty reason and message-clearing semantics
CODE_HASH: 700cd79d46dd
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->

# dag_storage interface component

## Purpose

The dag_storage interface component coordinates incremental workflow execution and inter-task diagnostic communication across multi-step agent runs.

Multi-step agent workflows require coordinated incremental execution to avoid redundant re-computation and prevent stale task outputs. As tasks evolve, dependent stages must understand why upstream changes necessitate re-execution, and downstream stages must communicate diagnostic issues back to their prerequisites. The dag_storage interface component provides a dedicated graph coordination boundary that isolates lifecycle tracking and inter-node communication state from the operational mechanics of individual task execution.

**Out of scope:** The dag_storage interface component does not execute node cleaning, enforce build policies, or schedule which nodes are visited; these are handled by other components.

## Types and Behavior

A *unit* is an end-artifact being worked on, and a *role* describes a phase of work done to an artifact.

A *dag node* identifies a discrete unit of work in the graph, having a unit address and a role address.

A system's *dag storage* stores node graph structure, node status, and messages.

A dag storage provides access to a node's *dag dependencies* and identifies whether each dependency is *silent*, precluding change message propagation from that dependency.

A *dag message* is text content explaining why a node requires cleaning, and is either a *change message* informing how an upstream dependency changed or a *feedback message* blaming a dependency target node for defects detected by downstream dependents.

A dag storage provides access to the messages recorded for a node, adds a feedback message blaming a dependency target node, materializes a template for a node whose source artifact is missing on disk, marks a node clean with a change message describing how the node changed, marks a node dirty, marks a subgraph clean, and reports whether a node is dirty.

A node is dirty when its source artifact is missing on disk, when its in-band metadata is missing or invalid, when it is marked dirty with a dirty tag, when it holds unacted feedback messages, or when a non-silent dependency was changed after the node was last cleaned.

A change message communicates how an upstream dependency changed, and is recorded on the dependent node when that node is marked clean.

Adding a feedback message records the critique in the blamed dependency target node's in-band metadata as unacted feedback.

Marking a node clean clears the messages recorded for the node and updates the in-band metadata of a node whose source artifact exists with a clean timestamp, clearing the node's unacted feedback and dirty tag. Marking a node clean with a change message for a node whose source artifact exists also writes the change message content as the node's change summary with a change timestamp.

Marking a node dirty removes the node's clean status and records the reason the node was marked dirty in its in-band metadata when one is provided.

Marking a subgraph clean materializes missing templates and marks the target node and every reachable dependency of the target node clean in graph storage.

Materializing a template for a node writes initial template content to disk when the node's source artifact is missing, preserving an existing source artifact without overwriting it.
