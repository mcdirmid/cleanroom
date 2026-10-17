<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-13T19:15:00Z
CHANGE: support non-blocking turn polling and optional timeout in antigravity harness
CODE_HASH: ffe0c10a017c
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->

# antigravity_harness interface component

imports: session, subagent_coordinator, subagent_harness

## Purpose

The antigravity_harness interface component defines data types and operational contracts for executing Cleanroom role turns through Google Antigravity and parsing transcript token telemetry.

Autonomous multi-agent execution requires reliable dispatch into isolated role workspaces, process management, and precise telemetry harvesting from platform event logs. The antigravity_harness interface component formalizes execution dispatch, transcript log parsing, token rate-card accounting, and role turn result construction for Google Antigravity.

**Out of scope:** The antigravity_harness interface component does not schedule multi-wave DAG queues or generate coordinator skills; these are handled by other components.

**Delegated:** Session lifecycle scoping is delegated to agent_session; harness adapter contracts and turn result models are delegated to subagent_coordinator; platform harness registration is delegated to subagent_harness.

## Types and Behavior

A *transcript token metrics* record captures uncached prompt tokens, cached prompt tokens, completion tokens, model name, and monetary expenditure in USD parsed from an Antigravity transcript log.

An abstract *transcript telemetry parser* reads execution logs and extracts model token consumption.

An *antigravity harness adapter* realizes the harness adapter protocol for Google Antigravity execution sessions.

An agent session's *antigravity harness manager* manages Antigravity execution adapters, installs the Antigravity adapter factory into the harness registry, and manages transcript parsing services.

When executing a role turn:

- The antigravity harness adapter dispatches the role directive into the target role workspace and monitors turn completion.

- The antigravity harness adapter polls active role turns non-blockingly to determine whether turn execution has concluded.

- The antigravity harness adapter extracts token usage metrics from the execution transcript log (parsing JSON objects or matching token metric patterns on raw transcript lines) and applies standard model pricing rate cards.

- The antigravity harness adapter inspects role workspace submission outcomes (including completion tags extracted from standard output) and blame buffers to construct a complete role turn result.

- The antigravity harness adapter interrupts active turns when execution deadlines are exceeded.
