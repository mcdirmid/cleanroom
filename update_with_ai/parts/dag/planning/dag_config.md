<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-05T04:28:01Z
LAST_CHANGED: 2026-10-04T23:01:55Z
CHANGE: new file
CODE_HASH: 2f1ca7090c63
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

## Woven Contracts

- The dag config exposes operational limits governing graph node visit caps and dirty node batch sizes during cleaning passes. [provide_node_visit_limit, provide_batch_size]
