# dsh_harness_impl implementation component

## Intent

Operating DeepSeek Harness within Autofab requires concrete process dispatch via the dsh CLI headless profile, active round supervision, event stream inspection, and standard rate-card calculations. Without concrete process and telemetry integration, DeepSeek Harness rounds cannot be invoked headlessly or evaluated for token cost. The dsh_harness_impl implementation component realizes the harness adapter and telemetry parser contracts for production DeepSeek Harness execution.

## Factored Contracts

### Typing

- The dsh telemetry parser realization implements DshTelemetryParser.
- The dsh harness adapter realization implements DshHarnessAdapter.
- The dsh harness manager realization implements DshHarnessManager and operates within the agent session tier.

### Contracts

- The telemetry parser realization parses JSON stream events or queries session storage archives to retrieve input tokens, output tokens, and cache read tokens. [query_dsh_telemetry_metrics]
- The telemetry parser realization applies pricing rates for the active model family to calculate USD expenditures. [apply_dsh_pricing_rates]
- The telemetry parser realization parses token metrics from stdout log text when structured records are absent. [parse_log_text_fallback]
- The harness adapter realization formats concise two-step task prompts directing workers strictly to read AGENTS.md in the workspace root if not already in context and run bin/get_work, omitting role labels, workspace paths, and explanatory ceremony, incorporates coordinator reminder directives when provided in role dispatch directives, derives initial pending targets in task memory from assigned ready targets or disk pending work without writing pending buffers to disk prior to worker execution, and evaluates whether the live DeepSeek Harness server is reachable. [prepare_task_prompt_and_pending_targets]
- The harness adapter realization dispatches role rounds over the local RPC bridge when the server is reachable (retrying transient connection failures and failing cleanly without incompatible headless CLI resumption, and renaming older role conversations to put `[<scope>] dead - <role>` after a replacement role conversation is issued to distinguish active role threads from obsolete ones), tracks candidate action log byte offsets prior to dispatch to isolate round-specific action records, or launches the dsh subprocess with overlay patches and non-interactive permissions when the server is absent. [spawn_dsh_round]
- The harness adapter realization polls and awaits round completion via RPC status or process termination without mandatory execution timeouts, terminating active executions only when an explicit timeout duration expires or when interrupted, aborting active RPC sessions via the session cancel endpoint without marking active role threads dead before a replacement exists, and killing headless processes upon interrupt, marking interrupted tasks for immediate non-blocking round harvesting during polling. [poll_and_await_dsh_round]
- The harness adapter realization compares pending work buffers, scrapes active session identifiers from event logs into workspace files for round continuity, tracks completed rounds per role workspace to recycle worker sessions after N rounds (defaulting to 4 rounds) with purged session IDs and baselines for a clean slate, resets session identifiers and round counts upon failed rounds (preserving session continuity across blamed rounds), inspects blame buffers, round logs, and candidate action logs across workspace root and scoped directories scanning only action records appended beyond pre-dispatch file offsets to identify newly submitted and blamed targets matching [CHANGE], [CLEAN], [SUBMITTED], and [AUDIT] action records, returning unresolved status when zero targets are submitted or blamed or when interrupted without clean completion, and calculates incremental round deltas from cumulative session token metrics across persistent session rounds to prevent double-counting. [compute_buffer_differences]
- The harness adapter realization publishes authoritative orchestration state snapshots capturing active scopes, current wave counts, active running workers with session identifiers and target files, idle completed workers (omitting roles that have never been invoked), dead sessions, and convergence status to external coordination storage (defaulting to autofab_state.json in DeepSeek Harness configuration storage) across role dispatch, round completion, and DAG convergence events. [publish_orchestration_state_snapshot]
- The harness manager realization provides singleton access to the telemetry parser, constructs configured harness adapter instances discovering session storage across environment overrides and platform conventions (defaulting to DeepSeek Harness Web storage strictly when Web mode is explicitly active), and installs the DeepSeek Harness adapter factory into the harness registry. [manage_dsh_harness_adapters]

### Woven Contracts

- When parsing session telemetry, the parser extracts metrics from event streams or storage archives, falls back to text logs, and applies model pricing. [query_dsh_telemetry_metrics, parse_log_text_fallback, apply_dsh_pricing_rates, dsh_harness: [extract_and_calculate_token_telemetry], dsh_telemetry: [query_dsh_telemetry_metrics, parse_log_text_fallback, apply_dsh_pricing_rates, sync_desktop_sessions]]
- When executing rounds, the adapter prepares prompts, evaluates server reachability, dispatches via RPC bridge or spawns subprocesses with overlay patches, polls and awaits lifecycle events, computes buffer differences, and publishes orchestration state snapshots. [prepare_task_prompt_and_pending_targets, spawn_dsh_round, poll_and_await_dsh_round, compute_buffer_differences, publish_orchestration_state_snapshot, dsh_harness: [dispatch_dsh_subagent_round, poll_and_await_dsh_round, inspect_blame_and_submitted_targets, formulate_role_round_result, publish_orchestration_state_snapshot]]
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
LAST_CLEANED: 2026-10-30T19:50:00Z
LAST_CHANGED: 2026-11-09T22:10:00Z
CHANGE: Authoritative orchestration state snapshot publishing to external coordination storage
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->
