<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T20:42:16Z
LAST_CHANGED: 2026-10-13T09:50:00Z
CHANGE: author goose_harness interface specification
CODE_HASH: d22371e13b42
SPEC_QA_AUDIT: 2026-10-13T20:42:16Z
-->

# goose_harness interface component

imports: agent_session, subagent_coordinator

## Purpose

The goose_harness interface component defines data types and operational contracts for executing Cleanroom role turns through Goose, managing context token compaction, and extracting session token telemetry.

Autonomous multi-agent execution requires reliable process management, context budgeting, and objective cost accounting across diverse agent hosts. Without dedicated harness contracts, Goose executions risk orphaned background processes, uncollected blame feedback, and missing token telemetry. The goose_harness interface component formalizes execution dispatch, process lifecycle control, session database telemetry parsing, and turn outcome aggregation for Goose.

**Out of scope:** The goose_harness interface component does not partition topological waves or evaluate DAG dirtiness; these are handled by other components.

**Delegated:** Session lifecycle scoping is delegated to agent_session; harness adapter protocols and turn outcome types are delegated to subagent_coordinator.

## Types and Behavior

A *goose token metrics* record captures uncached prompt tokens, cached prompt tokens, completion tokens, total tokens, model name, and monetary expenditure in USD parsed from Goose session storage.

An abstract *goose telemetry parser* extracts model token metrics from Goose session databases or execution logs.

A *goose harness adapter* realizes the harness adapter protocol for Goose execution sessions.

The *goose harness manager* of an agent session creates and manages Goose harness adapters and telemetry parsing services.

When executing a role turn:

- The goose harness adapter formats task prompts and dispatches Goose subagent processes within the designated role workspace directory, configuring context token compaction limits in the process environment.

- The goose harness adapter provides non-blocking polling and awaiting of process completion without mandatory execution timeouts, terminating active processes only when an explicit timeout limit is configured.

- The goose harness adapter inspects workspace blame buffers and pending work queues to determine blamed and submitted targets.

- The goose harness adapter extracts token telemetry from Goose session databases or execution output and calculates monetary expenditures using standard model pricing rate cards.

- The goose harness adapter produces a complete role turn result capturing status, submitted targets, blamed targets, failure diagnostics, token usage telemetry, and duration.
