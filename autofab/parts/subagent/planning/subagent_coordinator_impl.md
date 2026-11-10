# subagent_coordinator_impl implementation component

## Intent

The subagent_coordinator_impl implementation component realizes zero-execution multi-agent workspace coordination, dynamic queue-driven process supervision, fine-grained concurrency, and iterative loop convergence across external harness adapters.

## Factored Contracts

### Typing

- The subagent coordinator realization implements SubagentCoordinator and operates within agent_session.

### Contracts

- The realization resets preexisting role workspaces for declared roles upon initiating orchestration, restricting workspace provisioning and execution exclusively to a designated fused role when target_role resolves to a fused role definition. [reset_preexisting_role_workspaces]
- The realization resolves subagent batch sizes, conversation token limits, and maximum unproductive rounds thresholds from declarative model configurations matching designated model names or identifiers. [resolve_model_execution_parameters]
- The realization discovers commissioned workspaces and queries work queues via the work manager. [query_workspace_work_queues]
- The realization bounds work discovery and execution to a designated target unit and its transitive upstream dependencies when a target unit is specified. [bound_work_discovery_to_target_unit]
- The realization commissions absent role workspaces on demand via the workspace provisioner when ready tasks are identified, recording effective batch size limits into role descriptors. [commission_absent_workspaces]
- The realization dispatches role directives concurrently for roles possessing ready work, purging preexisting blame buffers from role workspaces, pulling updated files and refreshing system files from the canonical repository root and recording assigned ready targets in the pending work buffer prior to dispatch, tracking active worker handles without static wave partitioning, evaluating work queues on each polling interval to dispatch unblocked roles immediately while withholding downstream roles whose upstream dependencies on the same target unit are active or scheduled for concurrent dispatch. [dispatch_concurrent_role_workers]
- The realization periodically polls active workers through non-blocking checks on the configured harness adapter at a configurable interval (defaulting to 10 seconds), collecting role round results and consuming workspace blame buffers upon completion, enforcing an initialization grace period before evaluating idle worker state, interrupting idling workers that hold zero pending items across consecutive intervals past the grace period, and harvesting persistent idling workers directly when harness termination stalls. [poll_active_role_workers]
- The realization tracks consecutive unproductive rounds where a role yields zero submitted and zero blamed targets and assigned targets remain unresolved, suppressing unproductive counts and reminders when assigned targets are resolved, and halting orchestration when unproductive rounds exceed a threshold (defaulting to 5). [detect_unproductive_turn_impasse]
- The realization detects repeated identical blame delivery on unchanged targets, terminating and recommissioning worker workspaces on two consecutive identical blames and injecting a restart advisory into subsequent task prompts, halting orchestration upon exceeding 10 restarts, while clearing consecutive blame tracking when an author role submits modifications to a previously blamed target, and preventing concurrent dispatch of downstream roles on a target unit while upstream dependencies on the same target unit are actively executing or scheduled for concurrent dispatch. [detect_repeated_blame_circuit_breaker]
- The realization preserves unresolved reminder directives and injects them into the task prompts of subsequent role dispatch directives when workers complete rounds without submitting, blaming, or failing assigned targets and assigned targets remain unresolved (instructing workers to conclude with text and no tool calls once no work remains). [remind_worker_on_unresolved_round]
- The realization emits real-time progress notifications detailing role dispatch, round outcomes, token consumption, and work queue state, and notifies the execution harness adapter of authoritative orchestration state updates capturing active scopes, current wave counts, active running workers, idle completed workers, assigned targets, and convergence status to external coordination storage across role dispatch, round completion, and DAG convergence events. [emit_realtime_orchestration_telemetry]
- The realization manages the dynamic supervision loop, continuing until all units evaluate clean, a round reports failure, or maximum wave iterations are reached, draining or cleanly interrupting in-flight active workers upon termination. [drive_convergence_loop]
- The realization automatically deletes all provisioned role workspaces in scope upon achieving clean convergence, unless workspace retention is requested. [delete_role_workspaces_on_convergence]
- The realization interrupts active workers upon receiving cancellation signals. [interrupt_active_workers_on_cancellation]
- The realization deletes provisioned role workspaces in scope upon receiving cancellation signals. [decommission_workspaces_on_cancellation]
- The realization calculates token costs based on model pricing rate cards. [tally_turn_telemetry]
- The realization executes formal verification in the fused workspace upon worker completion, delivering diagnostics to the worker with up to 3 retries on failure, and atomically harvesting and marking targets clean on success. [verify_and_harvest_fused_workspace]

### Woven Contracts

- When initiating orchestration and managing convergence, the realization resets preexisting workspaces, resolves model parameters, drives the supervision loop, deletes provisioned workspaces upon clean convergence, cleans up upon cancellation, and verifies and harvests fused workspaces. [reset_preexisting_role_workspaces, resolve_model_execution_parameters, drive_convergence_loop, delete_role_workspaces_on_convergence, interrupt_active_workers_on_cancellation, decommission_workspaces_on_cancellation, verify_and_harvest_fused_workspace, subagent_coordinator: [reset_preexisting_role_workspaces, resolve_model_execution_parameters, orchestrate_pipeline_convergence, delete_role_workspaces_on_convergence, interrupt_active_workers_on_cancellation, decommission_workspaces_on_cancellation]]
- When supervising active workers, the realization queries work queues, bounds discovery to target units when specified, commissions absent workspaces, dispatches concurrent workers, polls active workers, detects unproductive turn impasses, detects repeated blame circuit breakers, reminds workers on unresolved rounds, emits real-time telemetry, and tallies turn telemetry. [query_workspace_work_queues, bound_work_discovery_to_target_unit, commission_absent_workspaces, dispatch_concurrent_role_workers, poll_active_role_workers, detect_unproductive_turn_impasse, detect_repeated_blame_circuit_breaker, remind_worker_on_unresolved_round, emit_realtime_orchestration_telemetry, tally_turn_telemetry, subagent_coordinator: [evaluate_ready_work_queues, commission_absent_workspaces, dispatch_concurrent_role_workers, poll_active_role_workers, detect_unproductive_turn_impasse, detect_repeated_blame_circuit_breaker, remind_worker_on_unresolved_round, emit_realtime_orchestration_telemetry, aggregate_cumulative_telemetry], provision: [commission_role_workspace], role_registry: [load_active_workspace_descriptors], sync: [pull_upstream_contracts, refresh_system_files_into_workspace], work: [compute_role_work_queue_targets, set_pending_work_targets]]

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
  - Grounded: [provision: [workspace_provisioning_service]]
- Role work queue computation and dirty target discovery services.
  - Grounded: [work: [workspace_work_discovery_service]]
- Active workspace registry and role discovery services.
  - Grounded: [role_registry: [workspace_registry_service]]
- Workspace file synchronization and inbound changes pulling services.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-11-06T02:49:00Z
LAST_CHANGED: 2026-11-09T22:10:00Z
CHANGE: Authoritative orchestration state updates across role dispatch, round completion, and convergence
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->
  - Grounded: [sync: [workspace_pull_service]]

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-11-06T02:49:00Z
LAST_CHANGED: 2026-11-06T02:49:00Z
CHANGE: Scope concurrent downstream role withholding to the active target unit
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->
