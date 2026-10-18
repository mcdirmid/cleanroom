<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-13T20:00:00Z
CHANGE: author dsh_harness_impl implementation specification
CODE_HASH: 412876414809
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->

# dsh_harness_impl implementation component

imports: session, dsh_ext, dsh_telemetry, subagent_coordinator, subagent_harness, work
implements: dsh_harness

## Purpose

The dsh_harness_impl implementation component realizes DeepSeek Harness subagent turn execution, process lifecycle control, and event stream / session storage telemetry harvesting.

Operating DeepSeek Harness within Cleanroom requires concrete process dispatch via the dsh CLI headless profile, active turn supervision, event stream inspection, and standard rate-card calculations. Without concrete process and telemetry integration, DeepSeek Harness turns cannot be invoked headlessly or evaluated for token cost. The dsh_harness_impl implementation component realizes the harness adapter and telemetry parser contracts for production DeepSeek Harness execution.

**Out of scope:** The dsh_harness_impl implementation component does not partition topological waves or evaluate DAG dirtiness; these are handled by other components.

**Delegated:** Session lifecycle scoping is delegated to agent_session; platform conventions are delegated to dsh_ext; harness adapter protocols and turn outcome types are delegated to subagent_coordinator; workspace work queue querying is delegated to work; token telemetry extraction and desktop session synchronization are delegated to dsh_telemetry; platform harness registration is delegated to subagent_harness.

## Types and Behavior

The dsh telemetry parser inspects DeepSeek Harness event streams and session storage archives to extract token metrics.

When parsing session telemetry:

- The dsh telemetry parser parses JSON stream events or queries session storage archives to retrieve recorded input tokens, output tokens, and cache read tokens.

- The dsh telemetry parser applies pricing rates for the active model family to compute total monetary expenditure in USD.

- The dsh telemetry parser parses text log streams as fallback when structured records are unavailable.

The dsh harness adapter executes DeepSeek Harness turns using configurable command lines within target role workspaces, discovering session storage across environment overrides and platform conventions.

When dispatching and awaiting role turns:

- The dsh harness adapter formats role-tailored task prompts distinguishing auditor roles from authoring roles, records initial pending targets seeded from ready targets, evaluates whether the live DeepSeek Harness server is reachable via the telemetry parser, and dispatches the turn over the local RPC bridge when reachable to stream real-time progress to the Desktop UI without file lock contention.

- When the live server is unreachable, the dsh harness adapter tests non-blocking file locks on session locks when adopting previously recorded session identifiers to prevent adoption collisions, launches the dsh CLI in the role workspace directory setting overlay patch parameters, session resumption arguments when available, and non-interactive permission flags, and tracks running process handles.

- The dsh harness adapter polls and awaits turn completion via RPC status responses or process termination without mandatory execution timeouts, terminating active executions only when an explicit timeout duration expires.

- The dsh harness adapter inspects workspace blame buffers and turn execution logs for attributed defects, computes submitted targets by comparing pending work buffers or action records, scrapes active session identifiers from event logs and saves them into role workspace files for turn continuity, records unresolved status when a completed turn produces zero submitted and zero blamed targets, and parses token metrics into normalized telemetry.

The dsh harness manager provides singleton access to the telemetry parser, constructs configured DeepSeek Harness adapters, and installs the DeepSeek Harness adapter factory into the harness registry.
