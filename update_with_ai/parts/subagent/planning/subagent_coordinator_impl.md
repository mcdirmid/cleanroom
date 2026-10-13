<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-12T23:37:36Z
LAST_CHANGED: 2026-10-12T21:00:00Z
CHANGE: author subagent_coordinator_impl planning specification
CODE_HASH: 3e0ed11fef53
SPEC_QA_AUDIT: 2026-10-12T23:37:36Z
-->

# subagent_coordinator_impl implementation component

## Intent

The subagent_coordinator_impl implementation component realizes zero-execution multi-agent workspace coordination, DAG wave partitioning, concurrent wave execution, and iterative loop convergence across external harness adapters.

## Factored Contracts

### Typing

- The subagent coordinator realization implements SubagentCoordinator and operates within agent_session.

### Contracts

- The realization discovers commissioned workspaces and queries work queues via the work manager. [query_workspace_work_queues]
- The realization commissions absent role workspaces via the workspace provisioner. [commission_absent_workspaces]
- The realization identifies unblocked dirty roles and partitions them into topological waves. [partition_topological_waves]
- The realization executes wave directives concurrently or sequentially through the harness adapter. [dispatch_wave_directives]
- The realization iterates through execution waves until DAG convergence or failure. [drive_convergence_loop]
- The realization calculates token costs based on model pricing rate cards. [tally_turn_telemetry]

### Woven Contracts

- When evaluating wave execution, the realization queries work queues, commissions absent workspaces, partitions waves, dispatches directives, and tallies turn telemetry. [query_workspace_work_queues, commission_absent_workspaces, partition_topological_waves, dispatch_wave_directives, tally_turn_telemetry, subagent_coordinator: [compute_execution_waves, commission_absent_workspaces, isolate_specification_roles, cluster_implementation_roles, execute_wave_roles], workspace_provision: [commission_role_workspace], workspace_registry: [load_active_workspace_descriptors], workspace_work: [compute_role_work_queue_targets]]
- When orchestrating convergence, the realization drives iterative waves until clean convergence or failure. [drive_convergence_loop, subagent_coordinator: [orchestrate_pipeline_convergence]]

## Grounding

### Knowledge Provisions

- Topological wave partitioning and role clustering logic. [topological_wave_partitioning]
- Multi-agent wave dispatch and await execution mechanics. [wave_dispatch_mechanics]
- Model rate card pricing and token usage aggregation. [rate_card_telemetry_tally]

### Inherited Deferred Requirements

- Subagent scheduling and wave execution logic.
  - Grounded: [topological_wave_partitioning, wave_dispatch_mechanics, rate_card_telemetry_tally]

### Knowledge Requirements

- Role workspace commissioning services.
  - Grounded: [workspace_provision: [workspace_provisioning_service]]
- Active workspace registry and role discovery services.
  - Grounded: [workspace_registry: [workspace_registry_service]]
- Role work queue computation and dirty target discovery services.
  - Grounded: [workspace_work: [workspace_work_discovery_service]]
