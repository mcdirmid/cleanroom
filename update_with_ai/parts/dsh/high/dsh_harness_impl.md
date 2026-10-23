# dsh_harness_impl implementation component

imports: session, dsh_ext, dsh_telemetry, subagent_coordinator, subagent_harness, work
implements: dsh_harness

## Purpose

The dsh_harness_impl implementation component realizes DeepSeek Harness subagent round execution, process lifecycle control, and event stream / session storage telemetry harvesting.

Operating DeepSeek Harness within Cleanroom requires concrete process dispatch via the dsh CLI headless profile, active round supervision, event stream inspection, and standard rate-card calculations. Without concrete process and telemetry integration, DeepSeek Harness rounds cannot be invoked headlessly or evaluated for token cost. The dsh_harness_impl implementation component realizes the harness adapter and telemetry parser contracts for production DeepSeek Harness execution.

**Out of scope:** The dsh_harness_impl implementation component does not partition topological waves or evaluate DAG dirtiness; these are handled by other components.

**Delegated:** Session lifecycle scoping is delegated to agent_session; platform conventions are delegated to dsh_ext; harness adapter protocols and round outcome types are delegated to subagent_coordinator; workspace work queue querying is delegated to work; token telemetry extraction and desktop session synchronization are delegated to dsh_telemetry; platform harness registration is delegated to subagent_harness.

## Types and Behavior

The dsh telemetry parser inspects DeepSeek Harness event streams and session storage archives to extract token metrics.

When parsing session telemetry:

- The dsh telemetry parser parses JSON stream events or queries session storage archives to retrieve recorded input tokens, output tokens, and cache read tokens.

- The dsh telemetry parser applies pricing rates for the active model family to compute total monetary expenditure in USD.

- The dsh telemetry parser parses text log streams as fallback when structured records are unavailable.

The dsh harness adapter executes DeepSeek Harness rounds using configurable command lines within target role workspaces, discovering session storage across environment overrides and platform conventions.

When dispatching and awaiting role rounds:

- The dsh harness adapter formats minimal, focused task prompts directing workers strictly to read AGENTS.md in the workspace root and discover pending work and companion guides via get_work without inlining target lists or dumping verbose boundary and workflow instructions into prompts, deferring role constraints and execution protocols to AGENTS.md and dynamic task binding to get_work, derives initial pending targets in task memory from assigned ready targets or disk pending work without writing pending buffers to disk prior to worker execution, evaluates whether the live DeepSeek Harness server is reachable via the telemetry parser, and dispatches the round over the local RPC bridge when reachable (retrying with exponential backoff on transient connection failures, and failing cleanly when desktop server RPC remains unreachable without attempting incompatible headless CLI fallback resumption) to stream real-time progress to the Desktop UI without file lock contention.

- When the live server is absent, the dsh harness adapter tests non-blocking file locks on session locks when adopting previously recorded session identifiers to prevent adoption collisions, launches the dsh CLI in the role workspace directory setting overlay patch parameters, session resumption arguments when available, and non-interactive permission flags, and tracks running process handles while writing round logs to `.cleanroom_round_{task_handle}.log`.

- The dsh harness adapter polls and awaits round completion via RPC status responses or process termination without mandatory execution timeouts, terminating active executions only when an explicit timeout duration expires.

- The dsh harness adapter inspects workspace blame buffers, round execution logs (checking `.cleanroom_round_{task_handle}.log` with fallback to `.cleanroom_turn_*.log`), and candidate cleanroom logs across workspace root and scoped directories (`**/.cleanroom.log`) for attributed defects, computes submitted targets by comparing pending work buffers or action records matching `[CHANGE]`, `[CLEAN]`, `[SUBMITTED]`, and `[AUDIT]`, scrapes active session identifiers from event logs and saves them into role workspace files for round continuity, resets session identifiers upon failed rounds to prevent context contamination loops (preserving session continuity across blamed rounds), records unresolved status when a completed round produces zero submitted and zero blamed targets, tracks session token baselines across rounds to calculate incremental round deltas from cumulative session metrics across persistent session rounds to prevent double-counting, evicts baselines upon session reset or failed rounds, and parses token metrics into normalized telemetry.

The dsh harness manager provides singleton access to the telemetry parser, constructs configured DeepSeek Harness adapters, and installs the DeepSeek Harness adapter factory into the harness registry.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-20T22:50:00Z
LAST_CHANGED: 2026-10-21T01:00:00Z
CHANGE: Track session token baselines and compute incremental round deltas from cumulative session metrics
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->
