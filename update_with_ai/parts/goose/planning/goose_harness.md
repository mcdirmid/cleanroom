<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T20:42:16Z
LAST_CHANGED: 2026-10-13T09:50:00Z
CHANGE: author goose_harness planning specification
CODE_HASH: 3c7cf7dfde12
SPEC_QA_AUDIT: 2026-10-13T20:42:16Z
-->

# goose_harness interface component

## Intent

Autonomous multi-agent execution requires reliable process management, timeout enforcement, and objective cost accounting across diverse agent hosts. Without dedicated harness contracts, Goose executions risk orphaned background processes, uncollected blame feedback, and missing token telemetry. The goose_harness interface component formalizes execution dispatch, process lifecycle control, session database telemetry parsing, and turn outcome aggregation for Goose.

## Factored Contracts

### Typing

- A goose token metrics record holds uncached prompt tokens, cached prompt tokens, completion tokens, total tokens, model name, and monetary cost in USD.
- A goose telemetry parser defines operations to extract token metrics from session databases and execution logs.
- A goose harness adapter realizes the coordinator harness adapter protocol for Goose sessions.
- A goose harness manager operates in the agent session tier and creates Goose harness adapters and manages telemetry parsing services.

### Contracts

- A goose harness adapter formats task prompts and dispatches Goose subagent processes within the designated role workspace directory, configuring context token compaction limits in the process environment. [dispatch_goose_subagent_process]
- A goose harness adapter provides non-blocking polling and awaiting of process completion without mandatory execution timeouts, terminating active processes only when an explicit timeout limit is configured. [poll_and_await_goose_process]
- A goose harness adapter inspects workspace blame buffers and pending work queues to determine blamed and submitted targets. [inspect_blame_and_submitted_targets]
- A goose harness adapter extracts token telemetry from Goose session databases or execution output and calculates monetary expenditures using standard model pricing rate cards. [extract_and_calculate_token_telemetry]
- A goose harness adapter produces a complete role turn result capturing status, submitted targets, blamed targets, failure diagnostics, token usage telemetry, and duration. [formulate_role_turn_result]

### Woven Contracts

- When executing a role turn, the harness adapter dispatches the subagent process, polls or awaits completion without mandatory execution timeouts, inspects blame buffers, extracts token telemetry, and formulates the role turn result. [dispatch_goose_subagent_process, poll_and_await_goose_process, inspect_blame_and_submitted_targets, extract_and_calculate_token_telemetry, formulate_role_turn_result, subagent_coordinator: [dispatch_concurrent_role_workers, poll_active_role_workers]]

## Grounding

### Knowledge Provisions

- Goose subagent execution, process supervision, and session telemetry harvesting services. [goose_harness_services]

### Knowledge Requirements

- Agent session lifecycle tier management.
  - Grounded: [agent_session: [agent_session_tier_provision]]
- Multi-agent workspace coordination services and wave scheduling.
  - Grounded: [subagent_coordinator: [subagent_coordinator_service]]
- Goose process execution, session database query, and turn result synthesis logic.
  - Deferred: Realized by the goose harness implementation component.
