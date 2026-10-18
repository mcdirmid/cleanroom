<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-13T20:00:00Z
CHANGE: author dsh_harness interface specification
CODE_HASH: ebe1d59209b4
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->

# dsh_harness interface component

imports: session, dsh_telemetry, subagent_coordinator, subagent_harness

## Purpose

The dsh_harness interface component defines data types and operational contracts for executing Cleanroom role turns through DeepSeek Harness, managing non-blocking process execution, and extracting session token telemetry.

Autonomous multi-agent execution requires reliable process management, non-blocking supervision, and objective cost accounting across diverse agent hosts. Without dedicated harness contracts, DeepSeek Harness executions risk orphaned background processes, uncollected blame feedback, and missing token telemetry. The dsh_harness interface component formalizes execution dispatch, process lifecycle control, session storage telemetry parsing, and turn outcome aggregation for DeepSeek Harness.

**Out of scope:** The dsh_harness interface component does not partition topological waves or evaluate DAG dirtiness; these are handled by other components.

**Delegated:** Session lifecycle scoping is delegated to agent_session; harness adapter protocols and turn outcome types are delegated to subagent_coordinator; token telemetry extraction, rate card calculation, and desktop session synchronization are delegated to dsh_telemetry; platform harness registration is delegated to subagent_harness.

## Types and Behavior

A *dsh token metrics* record captures uncached prompt tokens, cached prompt tokens, completion tokens, total tokens, model name, and monetary expenditure in USD parsed from DeepSeek Harness session storage or event streams.

An abstract *dsh telemetry parser* extracts model token metrics from DeepSeek Harness session storage or event log streams.

A *dsh harness adapter* realizes the harness adapter protocol for DeepSeek Harness execution sessions.

The *dsh harness manager* of an agent session creates and manages DeepSeek Harness adapters, installs the DeepSeek Harness adapter factory into the harness registry, and manages telemetry parsing services.

When executing a role turn:

- The dsh harness adapter formats task prompts, evaluates whether an active DeepSeek Harness server or Desktop application is reachable over the local RPC bridge, dispatches the turn over the RPC bridge when reachable to stream real-time progress to the Desktop UI without file lock contention, and falls back to dispatching headless subagent processes within the designated role workspace directory when unreachable.

- The dsh harness adapter provides non-blocking polling and awaiting of turn completion via the RPC bridge or process supervision without mandatory execution timeouts, terminating active executions only when an explicit timeout limit is configured.

- The dsh harness adapter inspects workspace blame buffers, turn execution logs, and pending work queues to determine blamed and submitted targets.

- The dsh harness adapter extracts token telemetry and active session identifiers from DeepSeek Harness event streams or session storage archives, persisting session identifiers for turn continuity and calculating monetary expenditures using standard model pricing rate cards.

- The dsh harness adapter produces a complete role turn result capturing status, submitted targets, blamed targets, failure diagnostics, token usage telemetry, and duration.
