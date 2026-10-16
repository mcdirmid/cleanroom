<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-12T21:00:00Z
CHANGE: author subagent_harness planning specification
CODE_HASH: 7dbf22244d86
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->

# subagent_harness interface component

## Intent

Multi-agent coordination requires dispatching autonomous agents into isolated role workspaces, instructing them with role directives, awaiting turn completion, and extracting outcome telemetry without coupling the central scheduler to platform-specific SDKs. Without a generalized process harness contract, each agent platform requires bespoke process management, inconsistent prompt formulation, and duplicate buffer inspection. The subagent_harness interface component formalizes command template execution, structured role prompt formulation, workspace pending and blame buffer inspection, process lifecycle control, and turn result synthesis.

## Factored Contracts

### Typing

- A command harness adapter realises the coordinator harness adapter protocol to execute role subagent turns through configurable process command templates.
- An adapter factory creates harness adapters configured with model name, timeout, context limits, custom command templates, or simulation mode.
- An agent session's harness registry maintains installed adapter factories by platform name, installs platform adapter factories, and resolves harness adapters for designated platform names, custom command templates, or simulation mode.

### Contracts

- The command harness adapter formats instructional task prompts detailing role, directory scope, targets, verification, and action commands. [format_subagent_task_prompt]
- The command harness adapter records initial pending targets prior to process execution. [capture_initial_pending_targets]
- The command harness adapter spawns external subagent processes matching configured command templates within the workspace directory, configuring context token compaction limits in the process environment. [spawn_subagent_process]
- The command harness adapter provides non-blocking polling and awaiting of process completion without mandatory execution timeouts, terminating stalled processes only when an explicit timeout limit is configured. [await_subagent_process_lifecycle]
- The command harness adapter inspects the workspace blame buffer for attributed defects. [inspect_workspace_blame_buffer]
- The command harness adapter determines submitted targets by set difference with remaining pending items. [determine_submitted_targets]
- The command harness adapter extracts token usage metrics from process log files. [extract_process_token_telemetry]
- The command harness adapter synthesizes role turn results containing status, submitted items, blamed items, telemetry, and diagnostics. [synthesize_role_turn_result]
- The harness registry installs adapter factories for platform names. [install_platform_harness_adapter]
- The harness registry resolves harness adapters by platform name, custom command template, or simulation mode. [resolve_platform_harness_adapter]

### Woven Contracts

- When executing a subagent turn, the command harness adapter formats instructional task prompts, captures initial pending targets, spawns subagent processes, awaits completion, inspects blame buffers, determines submitted targets, extracts token telemetry, and synthesizes role turn results. [format_subagent_task_prompt, capture_initial_pending_targets, spawn_subagent_process, await_subagent_process_lifecycle, inspect_workspace_blame_buffer, determine_submitted_targets, extract_process_token_telemetry, synthesize_role_turn_result, subagent_coordinator: [dispatch_concurrent_role_workers, poll_active_role_workers]]

## Grounding

### Knowledge Provisions

- Process-based subagent execution harness services. [command_harness_service]
- Platform harness registry services. [harness_registry_service]
- Platform harness adapter resolution services. [harness_resolver_service]

### Knowledge Requirements

- Agent session lifecycle tier management.
  - Grounded: [agent_session: [agent_session_tier_provision]]
- Coordinator harness adapter protocols and turn result types.
  - Grounded: [subagent_coordinator: [subagent_coordinator_service]]
- Cleanroom file conventions and buffer file names.
  - Deferred: Realized by the subagent harness implementation component.
- Subagent process execution and outcome synthesis.
  - Deferred: Realized by the subagent harness implementation component.
