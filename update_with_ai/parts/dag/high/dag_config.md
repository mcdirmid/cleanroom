# dag_config interface component

## Purpose

The dag_config interface component defines traversal limits and operational policies governing dependency graph cleaning passes.

Traversing dependency graphs during incremental builds risks circular evaluation loops and unbounded re-cleaning when inter-node dependencies trigger repeated invalidations. Centralizing traversal boundaries into a dedicated configuration service ensures deterministic graph walk limits across build executions. The dag_config interface component establishes an ambient system service that exposes operational constraints for graph cleaning workflows.

**Out of scope:** The dag_config interface component does not compute topological orderings, execute build actions, or communicate with language models; these are handled by other components.

## Types and Behavior

A *node visit limit* is a bound on the maximum number of times any node can be visited during dag cleaning.

The *dag config* is a system service that provides operational parameters for dependency graph execution.

The dag config provides:

- The node visit limit bounding node visits during graph cleaning.
