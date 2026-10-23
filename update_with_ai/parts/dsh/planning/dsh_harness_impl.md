# dsh_harness_impl implementation component

## Intent

Operating DeepSeek Harness within Cleanroom requires concrete process dispatch via the dsh CLI headless profile, active round supervision, event stream inspection, and standard rate-card calculations. Without concrete process and telemetry integration, DeepSeek Harness rounds cannot be invoked headlessly or evaluated for token cost. The dsh_harness_impl implementation component realizes the harness adapter and telemetry parser contracts for production DeepSeek Harness execution.

## Factored Contracts

### Typing

- The dsh telemetry parser realization implements DshTelemetryParser.
- The dsh harness adapter realization implements DshHarnessAdapter.
- The dsh harness manager realization implements DshHarnessManager and operates within the agent session tier.

### Contracts

- The telemetry parser realization parses JSON stream events or queries session storage archives to retrieve input tokens, output tokens, and cache read tokens. [query_dsh_telemetry_metrics]
- The telemetry parser realization applies pricing rates for the active model family to calculate USD expenditures. [apply_dsh_pricing_rates]
- The telemetry parser realization parses token metrics from stdout log text when structured records are absent. [parse_log_text_fallback]
- The harness adapter realization formats minimal, focused task prompts directing workers strictly to read AGENTS.md in the workspace root and discover pending work and companion guides via get_work without inlining target lists or dumping verbose instructions into prompts, incorporates coordinator reminder directives when provided in role dispatch directives, derives initial pending targets in task memory from assigned ready targets or disk pending work without writing pending buffers to disk prior to worker execution, and evaluates whether the live DeepSeek Harness server is reachable. [prepare_task_prompt_and_pending_targets]
- The harness adapter realization dispatches role rounds over the local RPC bridge when the server is reachable (retrying transient connection failures and failing cleanly without incompatible headless CLI resumption), or launches the dsh subprocess with overlay patches and non-interactive permissions when the server is absent. [spawn_dsh_round]
- The harness adapter realization polls and awaits round completion via RPC status or process termination without mandatory execution timeouts, terminating active executions only when an explicit timeout duration expires. [poll_and_await_dsh_round]
- The harness adapter realization compares pending work buffers, scrapes active session identifiers from event logs into workspace files for round continuity, resets session identifiers upon failed rounds (preserving session continuity across blamed rounds), inspects blame buffers, round logs, and candidate cleanroom logs across workspace root and scoped directories (.cleanroom.log) to identify submitted and blamed targets matching [CHANGE], [CLEAN], [SUBMITTED], and [AUDIT] action records, returning unresolved status when zero targets are submitted or blamed, and calculates incremental round deltas from cumulative session token metrics across persistent session rounds to prevent double-counting. [compute_buffer_differences]
- The harness manager realization provides singleton access to the telemetry parser, constructs configured harness adapter instances discovering session storage across environment overrides and platform conventions, and installs the DeepSeek Harness adapter factory into the harness registry. [manage_dsh_harness_adapters]

### Woven Contracts

- When parsing session telemetry, the parser extracts metrics from event streams or storage archives, falls back to text logs, and applies model pricing. [query_dsh_telemetry_metrics, parse_log_text_fallback, apply_dsh_pricing_rates, dsh_harness: [extract_and_calculate_token_telemetry], dsh_telemetry: [query_dsh_telemetry_metrics, parse_log_text_fallback, apply_dsh_pricing_rates, sync_desktop_sessions]]
- When executing rounds, the adapter prepares prompts, evaluates server reachability, dispatches via RPC bridge or spawns subprocesses with overlay patches, polls and awaits lifecycle events, and computes buffer differences. [prepare_task_prompt_and_pending_targets, spawn_dsh_round, poll_and_await_dsh_round, compute_buffer_differences, dsh_harness: [dispatch_dsh_subagent_round, poll_and_await_dsh_round, inspect_blame_and_submitted_targets, formulate_role_round_result]]
- When initializing, the harness manager realization installs the DeepSeek Harness adapter factory into the harness registry. [manage_dsh_harness_adapters, dsh_harness: [install_dsh_harness_adapter]]

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
  - Grounded: [work: [workspace_pending_work_tracking]]
- Subagent harness registry and adapter factory installation.
  - Grounded: [subagent_harness: [harness_registry_service]]
- DeepSeek Harness telemetry parsing and desktop synchronization services.
  - Grounded: [dsh_telemetry: [dsh_telemetry_services]]

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-20T22:50:00Z
LAST_CHANGED: 2026-10-21T01:00:00Z
CHANGE: Calculate incremental round deltas from cumulative session token metrics across persistent session rounds
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->
