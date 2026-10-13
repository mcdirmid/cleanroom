<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T20:42:16Z
LAST_CHANGED: 2026-10-13T09:50:00Z
CHANGE: author goose_harness_impl planning specification
CODE_HASH: 0f750d2b0cf9
SPEC_QA_AUDIT: 2026-10-13T20:42:16Z
-->

# goose_harness_impl implementation component

## Intent

Operating Goose within Cleanroom requires concrete process dispatch via the Goose CLI, active turn supervision, SQLite database inspection, and standard rate-card calculations. Without concrete process and database integration, Goose turns cannot be invoked headlessly or evaluated for token cost. The goose_harness_impl implementation component realizes the harness adapter and telemetry parser contracts for production Goose execution.

## Factored Contracts

### Typing

- The goose telemetry parser realization implements GooseTelemetryParser.
- The goose harness adapter realization implements GooseHarnessAdapter.
- The goose harness manager realization implements GooseHarnessManager and operates within the agent session tier.

### Contracts

- The telemetry parser realization queries the SQLite sessions database for input tokens, output tokens, and cache read tokens matching the session identifier or working directory. [query_session_db_metrics]
- The telemetry parser realization applies pricing rates for the resolved model family to calculate USD expenditures. [apply_goose_pricing_rates]
- The telemetry parser realization parses token metrics from stdout log text when database records are absent. [parse_log_text_fallback]
- The harness adapter realization writes task prompts and captures initial pending targets before spawning the Goose CLI. [prepare_task_prompt_and_pending_targets]
- The harness adapter realization launches the Goose subprocess in the role workspace directory, setting context token compaction environment variables, and tracks execution handles. [spawn_goose_subprocess]
- The harness adapter realization polls and awaits process termination without mandatory execution timeouts, terminating active subprocesses only when an explicit timeout duration expires. [poll_and_await_goose_subprocess]
- The harness adapter realization compares pending work buffers and inspects the blame buffer to identify submitted and blamed targets. [compute_buffer_differences]
- The harness manager realization provides singleton access to the telemetry parser and constructs configured harness adapter instances. [manage_goose_harness_adapters]

### Woven Contracts

- When parsing session telemetry, the parser queries the database, falls back to text logs, and applies model pricing. [query_session_db_metrics, parse_log_text_fallback, apply_goose_pricing_rates, goose_harness: [extract_and_calculate_token_telemetry]]
- When executing turns, the adapter prepares prompts, spawns subprocesses with compaction settings, polls and awaits lifecycle events, and computes buffer differences. [prepare_task_prompt_and_pending_targets, spawn_goose_subprocess, poll_and_await_goose_subprocess, compute_buffer_differences, goose_harness: [dispatch_goose_subagent_process, poll_and_await_goose_process, inspect_blame_and_submitted_targets, formulate_role_turn_result]]

## Grounding

### Knowledge Provisions

- Goose process lifecycle supervision and SQLite telemetry extraction mechanics. [goose_harness_mechanics]

### Inherited Deferred Requirements

- Goose process execution, session database query, and turn result synthesis logic.
  - Grounded: [goose_harness_mechanics]

### Knowledge Requirements

- Multi-agent workspace coordination services and wave scheduling.
  - Grounded: [subagent_coordinator: [subagent_coordinator_service]]
- Workspace pending work buffer inspection and tracking.
  - Grounded: [workspace_work: [workspace_pending_work_tracking]]
