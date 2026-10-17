<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-13T11:20:00Z
CHANGE: add workspace reset and convergence deletion contracts
CODE_HASH: dfa012840f40
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->

# subagent_coordinator_impl implementation component

## Intent

The subagent_coordinator_impl implementation component realizes zero-execution multi-agent workspace coordination, dynamic queue-driven process supervision, fine-grained concurrency, and iterative loop convergence across external harness adapters.

## Factored Contracts

### Typing

- The subagent coordinator realization implements SubagentCoordinator and operates within agent_session.

### Contracts

- The realization resets preexisting role workspaces for declared roles upon initiating orchestration. [reset_preexisting_role_workspaces]
- The realization resolves subagent batch sizes, conversation token limits, and maximum unproductive turns thresholds from declarative model configurations matching designated model names or identifiers. [resolve_model_execution_parameters]
- The realization discovers commissioned workspaces and queries work queues via the work manager. [query_workspace_work_queues]
- The realization commissions absent role workspaces on demand via the workspace provisioner when ready tasks are identified, recording effective batch size limits into role descriptors. [commission_absent_workspaces]
- The realization dispatches role directives concurrently for roles possessing ready work, tracking active worker handles without static wave partitioning. [dispatch_concurrent_role_workers]
- The realization periodically polls active workers through non-blocking checks on the configured harness adapter at a configurable interval (defaulting to 10 seconds), collecting role turn results upon completion. [poll_active_role_workers]
- The realization tracks consecutive unproductive turns where a role yields zero submitted and zero blamed targets, halting orchestration when unproductive turns exceed a threshold (defaulting to 5). [detect_unproductive_turn_impasse]
- The realization emits real-time progress notifications detailing role dispatch, turn outcomes, token consumption, and work queue state. [emit_realtime_orchestration_telemetry]
- The realization manages the dynamic supervision loop, continuing until all units evaluate clean, a turn reports failure, or maximum wave iterations are reached. [drive_convergence_loop]
- The realization automatically deletes all provisioned role workspaces in scope upon achieving clean convergence. [delete_role_workspaces_on_convergence]
- The realization calculates token costs based on model pricing rate cards. [tally_turn_telemetry]

### Woven Contracts

- When initiating orchestration and managing convergence, the realization resets preexisting workspaces, resolves model parameters, drives the supervision loop, and deletes provisioned workspaces upon clean convergence. [reset_preexisting_role_workspaces, resolve_model_execution_parameters, drive_convergence_loop, delete_role_workspaces_on_convergence, subagent_coordinator: [reset_preexisting_role_workspaces, resolve_model_execution_parameters, orchestrate_pipeline_convergence, delete_role_workspaces_on_convergence]]
- When supervising active workers, the realization queries work queues, commissions absent workspaces, dispatches concurrent workers, polls active workers, detects unproductive turn impasses, emits real-time telemetry, and tallies turn telemetry. [query_workspace_work_queues, commission_absent_workspaces, dispatch_concurrent_role_workers, poll_active_role_workers, detect_unproductive_turn_impasse, emit_realtime_orchestration_telemetry, tally_turn_telemetry, subagent_coordinator: [evaluate_ready_work_queues, commission_absent_workspaces, dispatch_concurrent_role_workers, poll_active_role_workers, detect_unproductive_turn_impasse, emit_realtime_orchestration_telemetry, aggregate_cumulative_telemetry], workspace_provision: [commission_role_workspace], workspace_registry: [load_active_workspace_descriptors], workspace_work: [compute_role_work_queue_targets]]

## Grounding

### Knowledge Provisions

- Workspace lifecycle management including initial reset and convergence deletion mechanics. [workspace_lifecycle_mechanics]
- Dynamic process supervision and queue-driven concurrency logic. [dynamic_process_supervision]
- Multi-agent dispatch and non-blocking polling mechanics. [worker_polling_mechanics]
- Model rate card pricing and token usage aggregation. [rate_card_telemetry_tally]

### Inherited Deferred Requirements

- Subagent scheduling, dynamic process supervision, and workspace lifecycle logic.
  - Grounded: [dynamic_process_supervision, worker_polling_mechanics, rate_card_telemetry_tally, workspace_lifecycle_mechanics]

### Knowledge Requirements

- Role workspace commissioning services.
  - Grounded: [workspace_provision: [workspace_provisioning_service]]
- Active workspace registry and role discovery services.
  - Grounded: [workspace_registry: [workspace_registry_service]]
- Role work queue computation and dirty target discovery services.
  - Grounded: [workspace_work: [workspace_work_discovery_service]]
