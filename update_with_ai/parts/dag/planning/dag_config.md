<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-12T18:21:03Z
LAST_CHANGED: 2026-10-11T02:58:44Z
CHANGE: Scope batch size to a cleaning batch and contract node visit limit enforcement
CODE_HASH: 5bcaa73822d0
SPEC_QA_AUDIT: 2026-10-12T18:21:03Z
-->

# dag_config interface component

## Intent

Traversing dependency graphs during incremental builds risks circular evaluation loops and unbounded re-cleaning when inter-node dependencies trigger repeated invalidations. Centralizing traversal boundaries into a dedicated configuration service ensures deterministic graph walk limits across build executions. The dag_config interface component establishes an ambient system service that exposes operational constraints for graph cleaning workflows.

By exposing explicit visit counts and role batching bounds, the component provides execution governors with the parameters needed to prevent infinite cleaning cycles.

## Factored Contracts

### Typing

- A node visit limit bounds the number of visits any node receives across dependency graph cleaning.
- A batch size bounds the number of dirty nodes of the same role address collected into a single cleaning batch.

### Contracts

- A system's dag config provides the node visit limit for dependency graph execution. [provide_node_visit_limit]
- A system's dag config provides the batch size for dependency graph execution. [provide_batch_size]
- The node visit limit is enforced when a subgraph records the visits of a cleaned batch. [enforce_node_visit_limit]

### Woven Contracts

- The dag config exposes operational limits governing graph node visit caps and dirty node batch sizes during cleaning passes. [provide_node_visit_limit, provide_batch_size]
- When a subgraph records the visits of a cleaned batch, the node visit limit is enforced. [provide_node_visit_limit, enforce_node_visit_limit]

## Grounding

### Knowledge Provisions

- Traversal boundaries exposing node visit limits and dirty batch size constraints. [dag_configuration_limits]

### Knowledge Requirements

- Operational limit configuration parameters from system environment or configuration models.
  - Deferred: Provided by system runtime configuration.
