<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-09T21:19:01Z
LAST_CHANGED: 2026-10-07T00:11:26Z
CHANGE: new file
CODE_HASH: ef965d10dc25
SPEC_QA_AUDIT: 2026-10-09T21:19:01Z
-->

# dag_config interface component

## Intent

Traversing dependency graphs during incremental builds risks circular evaluation loops and unbounded re-cleaning when inter-node dependencies trigger repeated invalidations. Centralizing traversal boundaries into a dedicated configuration service ensures deterministic graph walk limits across build executions. The dag_config interface component establishes an ambient system service that exposes operational constraints for graph cleaning workflows.

By exposing explicit visit counts and role batching bounds, the component provides execution governors with the parameters needed to prevent infinite cleaning cycles.

## Factored Contracts

### Typing

- A node visit limit bounds the maximum number of times any node can be visited during dag cleaning.
- A batch size bounds the maximum number of dirty nodes of the same role processed together in an agent session.

### Contracts

- A system's dag config provides the node visit limit for dependency graph execution. [provide_node_visit_limit]
- A system's dag config provides the batch size for dependency graph execution. [provide_batch_size]

### Woven Contracts

- The dag config exposes operational limits governing graph node visit caps and dirty node batch sizes during cleaning passes. [provide_node_visit_limit, provide_batch_size]

## Grounding

### Knowledge Provisions

- Traversal boundaries exposing node visit limits and dirty batch size constraints. [dag_configuration_limits]

### Knowledge Requirements

- Operational limit configuration parameters from system environment or configuration models.
  - Deferred: Provided by system runtime configuration.
