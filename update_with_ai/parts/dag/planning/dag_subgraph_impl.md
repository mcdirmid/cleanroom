<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T23:58:18Z
LAST_CHANGED: 2026-10-07T00:11:26Z
CHANGE: new file
CODE_HASH: 6b94b6228517
SPEC_QA_AUDIT: 2026-10-07T23:58:18Z
-->

# dag_subgraph_impl implementation component

imports: dag_config, dag_storage
implements: dag_subgraph

## Intent

Traversing multi-stage build workflows requires isolating reachable execution subgraphs, determining deterministic topological evaluation orders, and tracking node visitation bounds to prevent runaway re-cleaning cycles. When orchestrators implement ad-hoc graph walks, tie-breaking heuristics diverge and batching logic becomes fragmented across execution runners. The dag_subgraph_impl implementation component provides an in-memory graph index over dag storage that maintains deterministic dependency-first topological ordering, groups ready dirty nodes by role address up to configured batch limits, and enforces visit bounds across cleaning iterations.

By breaking topological sorting ties first by role tier depth and then by unit address, scheduling contiguous dirty nodes prioritized by dynamic role tier precedence (upstream roles before downstream roles determined dynamically from role dependency depth in the graph), and bounding node visitation against configured limits, the component ensures reliable and finite graph convergence.

## Factored Contracts

### Contracts

- The dag subgraph service breaks topological sorting ties by role tier depth first. [break_ties_by_role_tier_depth]
- The dag subgraph service breaks remaining topological sorting ties by unit address. [break_ties_by_unit_address]
- Dirty nodes in the next ready batch are contiguous in topological order. [ready_batch_contiguous_topological]
- Role tier precedence dynamically prioritizes upstream roles before downstream roles based on role dependency depth in the graph. [role_precedence_upstream_before_downstream]
- The next ready batch starts from the earliest ready dirty node in topological order. [ready_batch_starts_from_earliest]
- The maximum batch size is obtained from dag config. [batch_size_obtained_from_config]
- When no dirty node in the target subgraph has all its dependencies in the target subgraph clean in dag storage, the next ready batch is an empty sequence. [empty_batch_when_no_dependencies_clean]
- Recording a visit advances the visit count for each node in the batch. [advance_node_visit_counts]
- The node visit limit is obtained from dag config. [visit_limit_obtained_from_config]
- When any node in the batch exceeds the node visit limit, recording a visit raises an unexpected failure. [fail_when_visit_limit_exceeded]

### Woven Contracts

- When sorting reachable dependency nodes in topological order, ties are broken by role tier depth first, then by unit address. [break_ties_by_role_tier_depth, break_ties_by_unit_address, dag_subgraph: [compute_topological_order]]
- When selecting the next ready batch, contiguous dirty nodes of the same role address starting from the earliest ready dirty node are collected up to the batch size configured in dag config. [ready_batch_contiguous_topological, ready_batch_starts_from_earliest, batch_size_obtained_from_config, dag_config: [provide_batch_size], dag_subgraph: [provide_next_ready_batch, ready_batch_grouped_by_role, ready_batch_bounded_by_size]]
- When prioritizing ready dirty nodes, role tiers are scheduled dynamically with upstream roles before downstream roles based on role dependency depth in the graph. [role_precedence_upstream_before_downstream, dag_subgraph: [ready_batch_prioritized_by_role_tier]]
- When no dirty node in the target subgraph has all its dependencies clean in dag storage, an empty sequence is returned. [empty_batch_when_no_dependencies_clean, dag_subgraph: [provide_next_ready_batch], dag_storage: [expose_node_dirty]]
- When recording a visit advances any node's count beyond the limit configured in dag config, an unexpected failure is raised. [advance_node_visit_counts, visit_limit_obtained_from_config, fail_when_visit_limit_exceeded, dag_config: [provide_node_visit_limit], dag_subgraph: [record_visit_increment_counts, record_visit_enforce_iteration_limits]]

## Grounding

### Knowledge Provisions

- Dependency-first topological subgraph queries, ready batch scheduling, and visit tracking. [dag_subgraph_service]

### Inherited Deferred Requirements

- Direct dependency graph traversal and node dirty status checks.
  - Grounded: [dag_storage: [dag_storage_service]]
- Traversal boundaries for batch size and node visit limits.
  - Grounded: [dag_config: [dag_configuration_limits]]

### Knowledge Requirements

- Topological sorting with role tier and unit address tie-breaking.
  - Grounded: [dag_storage: [dag_storage_service]]
- Grouping contiguous ready dirty nodes by role address up to configured batch size.
  - Grounded: [dag_storage: [dag_storage_service], dag_config: [dag_configuration_limits]]
- Visit count tracking and limit enforcement raising unexpected failures when exceeded.
  - Grounded: [dag_config: [dag_configuration_limits]]
