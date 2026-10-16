<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-11T01:39:02Z
CHANGE: Scope batch size to a cleaning batch and name the enforcing operations
CODE_HASH: cfe5315de365
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->

# dag_config interface component

## Purpose

The dag_config interface component defines traversal limits and operational policies governing dependency graph cleaning passes.

Traversing dependency graphs during incremental builds risks circular evaluation loops and unbounded re-cleaning when inter-node dependencies trigger repeated invalidations. Centralizing traversal boundaries into a dedicated configuration service ensures deterministic graph walk limits across build executions. The dag_config interface component establishes an ambient system service that exposes operational constraints for graph cleaning workflows.

**Out of scope:** The dag_config interface component does not compute topological orderings, execute build actions, or communicate with language models; these are handled by other components.

## Types and Behavior

A *node visit limit* bounds the number of visits any node receives across dependency graph cleaning, and is enforced when a subgraph records the visits of a cleaned batch.

A *batch size* bounds the number of dirty nodes of the same role address collected into a single cleaning batch.

A system's *dag config* provides the node visit limit and the batch size for dependency graph execution.
