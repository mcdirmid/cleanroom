<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T20:42:16Z
LAST_CHANGED: 2026-10-13T20:00:00Z
CHANGE: author dsh_harness_impl planning specification
CODE_HASH: cdd1fe55aa7d
SPEC_QA_AUDIT: 2026-10-13T20:42:16Z
-->

# dsh_harness_impl implementation component

## Intent

Operating DeepSeek Harness within Cleanroom requires concrete process dispatch via the dsh CLI headless profile, active turn supervision, event stream inspection, and standard rate-card calculations. Without concrete process and telemetry integration, DeepSeek Harness turns cannot be invoked headlessly or evaluated for token cost. The dsh_harness_impl implementation component realizes the harness adapter and telemetry parser contracts for production DeepSeek Harness execution.

## Factored Contracts

### Typing

- The dsh telemetry parser realization implements DshTelemetryParser.
- The dsh harness adapter realization implements DshHarnessAdapter.
- The dsh harness manager realization implements DshHarnessManager and operates within the agent session tier.

### Contracts

- The telemetry parser realization parses JSON stream events or queries session storage archives to retrieve input tokens, output tokens, and cache read tokens. [query_dsh_telemetry_metrics]
- The telemetry parser realization applies pricing rates for the active model family to calculate USD expenditures. [apply_dsh_pricing_rates]
- The telemetry parser realization parses token metrics from stdout log text when structured records are absent. [parse_log_text_fallback]
- The harness adapter realization writes task prompts and captures initial pending targets before spawning the dsh CLI. [prepare_task_prompt_and_pending_targets]
- The harness adapter realization launches the dsh subprocess in the role workspace directory, setting overlay patch parameters and non-interactive permission flags, and tracks execution handles. [spawn_dsh_subprocess]
- The harness adapter realization polls and awaits process termination without mandatory execution timeouts, terminating active subprocesses only when an explicit timeout duration expires. [poll_and_await_dsh_subprocess]
- The harness adapter realization compares pending work buffers and inspects the blame buffer to identify submitted and blamed targets. [compute_buffer_differences]
- The harness manager realization provides singleton access to the telemetry parser and constructs configured harness adapter instances. [manage_dsh_harness_adapters]

### Woven Contracts

- When parsing session telemetry, the parser extracts metrics from event streams or storage archives, falls back to text logs, and applies model pricing. [query_dsh_telemetry_metrics, parse_log_text_fallback, apply_dsh_pricing_rates, dsh_harness: [extract_and_calculate_token_telemetry]]
- When executing turns, the adapter prepares prompts, spawns subprocesses with overlay patches, polls and awaits lifecycle events, and computes buffer differences. [prepare_task_prompt_and_pending_targets, spawn_dsh_subprocess, poll_and_await_dsh_subprocess, compute_buffer_differences, dsh_harness: [dispatch_dsh_subagent_process, poll_and_await_dsh_process, inspect_blame_and_submitted_targets, formulate_role_turn_result]]

## Grounding

### Knowledge Provisions

- DeepSeek Harness process lifecycle supervision and telemetry extraction mechanics. [dsh_harness_mechanics]

### Inherited Deferred Requirements

- DeepSeek Harness process execution, session storage parsing, and turn result synthesis logic.
  - Grounded: [dsh_harness_mechanics]

### Knowledge Requirements

- Multi-agent workspace coordination services and wave scheduling.
  - Grounded: [subagent_coordinator: [subagent_coordinator_service]]
- Workspace pending work buffer inspection and tracking.
  - Grounded: [workspace_work: [workspace_pending_work_tracking]]
