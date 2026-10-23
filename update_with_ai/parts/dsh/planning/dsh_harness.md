# dsh_harness interface component

## Intent

Autonomous multi-agent execution requires reliable process management, non-blocking supervision, and objective cost accounting across diverse agent hosts. Without dedicated harness contracts, DeepSeek Harness executions risk orphaned background processes, uncollected blame feedback, and missing token telemetry. The dsh_harness interface component formalizes execution dispatch, process lifecycle control, session storage telemetry parsing, and round outcome aggregation for DeepSeek Harness.

## Factored Contracts

### Typing

- A dsh token metrics record holds uncached prompt tokens, cached prompt tokens, completion tokens, total tokens, model name, and monetary cost in USD.
- A dsh telemetry parser defines operations to extract token metrics from session storage archives and execution event logs.
- A dsh harness adapter realizes the coordinator harness adapter protocol for DeepSeek Harness sessions.
- A dsh harness manager operates in the agent session tier, creates DeepSeek Harness adapters, installs the DeepSeek Harness adapter factory into the harness registry, and manages telemetry parsing services.

### Contracts

- A dsh harness adapter formats task prompts, evaluates server reachability, dispatches role rounds over the local RPC bridge when reachable, and falls back to dispatching headless subagent processes within the designated role workspace directory. [dispatch_dsh_subagent_round]
- A dsh harness adapter provides non-blocking polling and awaiting of round completion via the RPC bridge or process supervision without mandatory execution timeouts, terminating active executions only when an explicit timeout limit is configured. [poll_and_await_dsh_round]
- A dsh harness adapter inspects workspace blame buffers, round logs, and pending work queues to determine blamed and submitted targets. [inspect_blame_and_submitted_targets]
- A dsh harness adapter extracts token telemetry from DeepSeek Harness event streams or session storage archives, calculates incremental round deltas from cumulative session metrics across persistent session rounds to prevent double-counting, and calculates monetary expenditures using standard model pricing rate cards. [extract_and_calculate_token_telemetry]
- A dsh harness adapter produces a complete role round result capturing status, submitted targets, blamed targets, failure diagnostics, token usage telemetry, and duration. [formulate_role_round_result]
- A dsh harness manager installs the DeepSeek Harness adapter factory into the harness registry. [install_dsh_harness_adapter]

### Woven Contracts

- When executing a role round, the harness adapter dispatches the subagent round over RPC or headless CLI, polls or awaits completion without mandatory execution timeouts, inspects blame buffers, extracts token telemetry, and formulates the role round result. [dispatch_dsh_subagent_round, poll_and_await_dsh_round, inspect_blame_and_submitted_targets, extract_and_calculate_token_telemetry, formulate_role_round_result, subagent_coordinator: [dispatch_concurrent_role_workers, poll_active_role_workers]]

## Grounding

### Knowledge Provisions

- DeepSeek Harness subagent execution, process supervision, and session telemetry harvesting services. [dsh_harness_services]

### Knowledge Requirements

- Agent session lifecycle tier management.
  - Grounded: [session: [agent_session_tier_provision]]
- Multi-agent workspace coordination services and wave scheduling.
  - Grounded: [subagent_coordinator: [subagent_coordinator_service]]
- Subagent harness registry and adapter factory installation.
  - Grounded: [subagent_harness: [harness_registry_service]]
- DeepSeek Harness process execution, session storage parsing, and turn result synthesis logic.
  - Deferred: Realized by the dsh harness implementation component.
- DeepSeek Harness telemetry parsing and desktop synchronization services.
  - Grounded: [dsh_telemetry: [dsh_telemetry_services]]

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-21T01:00:00Z
CHANGE: Calculate incremental round deltas from cumulative session metrics across persistent session rounds
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->
