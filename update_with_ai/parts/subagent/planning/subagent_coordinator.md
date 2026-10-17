<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-13T11:20:00Z
CHANGE: add workspace reset and convergence deletion contracts
CODE_HASH: 19689d905946
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->

# subagent_coordinator interface component

## Intent

Complex software development methodologies partition work into specialized roles that depend on upstream artifacts. Executing these roles with rigid static waves or hardcoded role assumptions leads to artificial serialization, idle worker capacity, and invalidated context. The subagent_coordinator interface component formalizes dynamic queue-driven process supervision, fine-grained node concurrency, harness abstraction, turn result aggregation, blame defect propagation, model configuration resolution, and cumulative token rate-card accounting.

## Factored Contracts

### Typing

- A token usage record reports input tokens, cached tokens, output tokens, total tokens, and monetary cost in USD.
- A role dispatch directive holds role name, workspace directory, directory scope, ready targets, batch size, and instructional task prompt.
- A role turn result reports turn status, submitted targets, blamed targets, failure diagnostics, token telemetry, and elapsed wall-clock duration.
- An orchestration summary reports convergence status, total waves, submitted count, blamed count, total telemetry, and diagnostic status messages.
- A coordinator harness adapter defines dispatch, non-blocking polling, await, and interrupt methods for subagents.
- A subagent coordinator schedules subagents across role workspaces within an agent session.

### Contracts

- A subagent coordinator resets preexisting role workspaces upon initiating orchestration to ensure clean initial state. [reset_preexisting_role_workspaces]
- A subagent coordinator dynamically resolves subagent batch sizes, conversation token limits, and maximum unproductive turns thresholds from declarative model configurations matching designated model names or identifiers. [resolve_model_execution_parameters]
- A subagent coordinator evaluates DAG work queues across declared roles, dynamically identifying roles with ready work up to an optional target role boundary without static role hardcoding. [evaluate_ready_work_queues]
- A subagent coordinator ensures absent role workspaces are commissioned via workspace provisioning on demand before dispatching directives, persisting effective batch size bounds into workspace configurations. [commission_absent_workspaces]
- A subagent coordinator dispatches role directives to unblocked ready roles concurrently, tracking active worker handles without static wave partitioning. [dispatch_concurrent_role_workers]
- A subagent coordinator periodically polls active workers through the harness adapter at a configurable polling interval (defaulting to 10 seconds), reaping completed turns and propagating blame defects into the build graph. [poll_active_role_workers]
- A subagent coordinator tracks consecutive unproductive turns yielding zero submitted and zero blamed targets, halting orchestration when unproductive turns on unresolved targets exceed a threshold (defaulting to 5). [detect_unproductive_turn_impasse]
- A subagent coordinator emits real-time progress notifications detailing role dispatch, turn outcomes, token consumption, and work queue state. [emit_realtime_orchestration_telemetry]
- A subagent coordinator drives the supervision loop until all units in scope evaluate clean, a role reports failure, or maximum wave limits are reached. [orchestrate_pipeline_convergence]
- A subagent coordinator automatically deletes all provisioned role workspaces in scope upon achieving clean convergence. [delete_role_workspaces_on_convergence]
- A subagent coordinator aggregates cumulative token consumption into monetary expenditures across all dispatched roles. [aggregate_cumulative_telemetry]

### Woven Contracts

- When initiating orchestration, the coordinator resets preexisting role workspaces, resolves model execution parameters, and drives pipeline convergence until clean convergence or failure. [reset_preexisting_role_workspaces, resolve_model_execution_parameters, orchestrate_pipeline_convergence, delete_role_workspaces_on_convergence]
- When evaluating work queues, the coordinator commissions absent workspaces with batch size bounds and dispatches concurrent role workers without static wave partitioning. [evaluate_ready_work_queues, commission_absent_workspaces, dispatch_concurrent_role_workers]
- When supervising active workers, the coordinator periodically polls active workers through the harness adapter, detects unproductive turn impasses, emits real-time telemetry, and aggregates cumulative telemetry. [poll_active_role_workers, detect_unproductive_turn_impasse, emit_realtime_orchestration_telemetry, aggregate_cumulative_telemetry]

## Grounding

### Knowledge Provisions

- Multi-agent workspace coordination services and dynamic supervision. [subagent_coordinator_service]
- Harness adapter execution protocol and turn outcome types. [harness_adapter_protocol]

### Knowledge Requirements

- Agent session lifecycle tier management.
  - Grounded: [session: [agent_session_tier_provision]]
- Subagent scheduling, dynamic process supervision, and workspace lifecycle logic.
  - Deferred: Realized by the subagent coordinator implementation component.
