<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-12T23:37:36Z
LAST_CHANGED: 2026-10-12T21:00:00Z
CHANGE: author subagent_coordinator planning specification
CODE_HASH: 4a4a4e2ae2dd
SPEC_QA_AUDIT: 2026-10-12T23:37:36Z
-->

# subagent_coordinator interface component

## Intent

Complex software development methodologies partition work into specialized roles that depend on upstream artifacts. Executing these roles concurrently without ordering guarantees leads to cache thrashing, race conditions, and invalidated context. The subagent_coordinator interface component formalizes topological wave clustering, parallel and sequential execution waves, harness abstraction, turn result aggregation, blame defect propagation, and cumulative token rate-card accounting.

## Factored Contracts

### Typing

- A token usage record reports input tokens, cached tokens, output tokens, total tokens, and monetary cost in USD.
- A role dispatch directive holds role name, workspace directory, directory scope, ready targets, batch size, and instructional task prompt.
- A role turn result reports turn status, submitted targets, blamed targets, failure diagnostics, token telemetry, and elapsed wall-clock duration.
- An orchestration summary reports convergence status, total waves, submitted count, blamed count, total telemetry, and diagnostic status messages.
- A coordinator harness adapter defines abstract dispatch, await, and interrupt methods for subagents.
- A subagent coordinator schedules subagents across role workspaces within an agent session.

### Contracts

- A subagent coordinator computes execution waves by grouping unblocked dirty roles into topological partitions. [compute_execution_waves]
- A subagent coordinator ensures absent role workspaces are commissioned before scheduling dispatch directives. [commission_absent_workspaces]
- A subagent coordinator separates sequential specification roles into single-role waves. [isolate_specification_roles]
- A subagent coordinator combines independent unblocked implementation roles into parallel execution waves. [cluster_implementation_roles]
- A subagent coordinator dispatches all roles in an execution wave through the harness adapter and awaits results. [execute_wave_roles]
- A subagent coordinator drives the multi-wave convergence loop until all units in scope evaluate clean, a turn fails, or max waves is reached. [orchestrate_pipeline_convergence]

### Woven Contracts

- When computing execution waves, the coordinator commissions absent workspaces and partitions sequential specification roles from parallel implementation roles. [compute_execution_waves, commission_absent_workspaces, isolate_specification_roles, cluster_implementation_roles]
- When orchestrating pipeline convergence, the coordinator iteratively computes waves and executes them through the harness adapter. [orchestrate_pipeline_convergence, compute_execution_waves, execute_wave_roles]

## Grounding

### Knowledge Provisions

- Multi-agent workspace coordination services and wave scheduling. [subagent_coordinator_service]
- Harness adapter execution protocol and turn outcome types. [harness_adapter_protocol]

### Knowledge Requirements

- Agent session lifecycle tier management.
  - Grounded: [agent_session: [agent_session_tier_provision]]
- Subagent scheduling and wave execution logic.
  - Deferred: Realized by the subagent coordinator implementation component.
