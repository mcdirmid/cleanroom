# subagent_coordinator interface component

## Intent

Complex software development methodologies partition work into specialized roles that depend on upstream artifacts. Executing these roles with rigid static waves or hardcoded role assumptions leads to artificial serialization, idle worker capacity, and invalidated context. The subagent_coordinator interface component formalizes dynamic queue-driven process supervision, fine-grained node concurrency, harness abstraction, round result aggregation, blame defect propagation, model configuration resolution, and cumulative token rate-card accounting.

## Factored Contracts

### Typing

- A token usage record reports input tokens, cached tokens, output tokens, total tokens, and monetary cost in USD.
- A role dispatch directive holds role name, workspace directory, directory scope, ready targets, batch size, and instructional task prompt.
- A role round result reports round status, submitted targets, blamed targets, failure diagnostics, token telemetry, and elapsed wall-clock duration.
- An orchestration summary reports convergence status, total waves, submitted count, blamed count, total telemetry, and diagnostic status messages.
- A coordinator harness adapter defines dispatch, non-blocking polling, await, and interrupt methods for subagents.
- A subagent coordinator schedules subagents across role workspaces within an agent session.

### Contracts

- A subagent coordinator resets preexisting role workspaces upon initiating orchestration to ensure clean initial state. [reset_preexisting_role_workspaces]
- A subagent coordinator dynamically resolves subagent batch sizes, conversation token limits, and maximum unproductive rounds thresholds from declarative model configurations matching designated model names or identifiers. [resolve_model_execution_parameters]
- A subagent coordinator evaluates DAG work queues across declared roles, dynamically identifying roles with ready work up to an optional target role boundary without static role hardcoding. [evaluate_ready_work_queues]
- A subagent coordinator restricts work queue evaluation to a designated target unit and its transitive upstream dependencies when a target unit is specified. [bound_evaluation_to_target_unit]
- A subagent coordinator ensures absent role workspaces are commissioned via workspace provisioning on demand before dispatching directives, persisting effective batch size bounds into workspace configurations. [commission_absent_workspaces]
- A subagent coordinator dispatches role directives to unblocked ready roles concurrently, tracking active worker handles without static wave partitioning. [dispatch_concurrent_role_workers]
- A subagent coordinator periodically polls active workers through the harness adapter at a configurable polling interval (defaulting to 10 seconds), reaping completed rounds and propagating blame defects into the build graph. [poll_active_role_workers]
- A subagent coordinator tracks consecutive unproductive rounds yielding zero submitted and zero blamed targets, halting orchestration when unproductive rounds on unresolved targets exceed a threshold (defaulting to 5). [detect_unproductive_turn_impasse]
- A subagent coordinator injects an actionable reminder directive into subsequent role dispatch directives when an active worker completes a round without submitting, blaming, or failing assigned targets, reminding the worker that conversational commentary without tools is prohibited and requiring verification and resolution via submit, blame, or fail. [remind_worker_on_unresolved_round]
- A subagent coordinator emits real-time progress notifications detailing role dispatch, round outcomes, token consumption, and work queue state. [emit_realtime_orchestration_telemetry]
- A subagent coordinator drives the supervision loop until all units in scope evaluate clean, a role reports failure, or maximum wave limits are reached. [orchestrate_pipeline_convergence]
- A subagent coordinator automatically deletes all provisioned role workspaces in scope upon achieving clean convergence. [delete_role_workspaces_on_convergence]
- A subagent coordinator interrupts active workers upon receiving cancellation signals. [interrupt_active_workers_on_cancellation]
- A subagent coordinator deletes provisioned role workspaces in scope upon receiving cancellation signals. [decommission_workspaces_on_cancellation]
- A subagent coordinator aggregates cumulative token consumption into monetary expenditures across all dispatched roles. [aggregate_cumulative_telemetry]

### Woven Contracts

- When initiating orchestration, the coordinator resets preexisting role workspaces, resolves model execution parameters, drives pipeline convergence until clean convergence or failure, and cleans up upon cancellation. [reset_preexisting_role_workspaces, resolve_model_execution_parameters, orchestrate_pipeline_convergence, delete_role_workspaces_on_convergence, interrupt_active_workers_on_cancellation, decommission_workspaces_on_cancellation]
- When evaluating work queues, the coordinator commissions absent workspaces with batch size bounds, restricts evaluation to target units when specified, and dispatches concurrent role workers without static wave partitioning. [evaluate_ready_work_queues, bound_evaluation_to_target_unit, commission_absent_workspaces, dispatch_concurrent_role_workers]
- When supervising active workers, the coordinator periodically polls active workers through the harness adapter, detects unproductive turn impasses, reminds workers on unresolved rounds, emits real-time telemetry, and aggregates cumulative telemetry. [poll_active_role_workers, detect_unproductive_turn_impasse, remind_worker_on_unresolved_round, emit_realtime_orchestration_telemetry, aggregate_cumulative_telemetry]

## Grounding

### Knowledge Provisions

- Multi-agent workspace coordination services and dynamic supervision. [subagent_coordinator_service]
- Harness adapter execution protocol and round outcome types. [harness_adapter_protocol]

### Knowledge Requirements

- Agent session lifecycle tier management.
  - Grounded: [session: [agent_session_tier_provision]]
- Subagent scheduling, dynamic process supervision, and workspace lifecycle logic.
  - Deferred: Realized by the subagent coordinator implementation component.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-18T01:30:00Z
CHANGE: support restricting work queue evaluation to target units and transitive dependencies
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->
