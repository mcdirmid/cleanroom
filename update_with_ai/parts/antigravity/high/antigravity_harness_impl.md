<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T01:05:05Z
LAST_CHANGED: 2026-10-12T21:45:00Z
CHANGE: author antigravity_harness_impl implementation specification
CODE_HASH: 01453c746b54
SPEC_QA_AUDIT: 2026-10-13T01:05:05Z
-->

# antigravity_harness_impl implementation component

imports: agent_session, antigravity_ext, antigravity_harness, subagent_coordinator
implements: antigravity_harness

## Purpose

The antigravity_harness_impl implementation component realizes subagent turn execution, JSONL transcript telemetry parsing, and Gemini rate-card cost calculation for Google Antigravity.

Harvesting accurate token telemetry from local execution logs and managing subprocess lifecycles requires specialized parsing and cost calculation algorithms. The antigravity_harness_impl implementation component provides transcript parsing, subprocess management, and standardized financial rate cards.

**Out of scope:** The antigravity_harness_impl implementation component does not schedule multi-wave DAG queues or generate coordinator skills; these are handled by other components.

**Delegated:** Session lifecycle scoping is delegated to agent_session; log format schemas are delegated to antigravity_ext; interface definitions are delegated to antigravity_harness; role dispatch contracts and turn result types are delegated to subagent_coordinator.

## Types and Behavior

The antigravity harness manager realization manages Antigravity execution adapters and transcript parsing services.

When executing a role turn:

- The realization spawns the Antigravity subagent process bound to the role workspace directory.

- The realization parses JSONL event lines from the transcript log to extract model token usage.

- The realization computes monetary costs using standard rate cards for Gemini Flash and Gemini Pro models.

- The realization collects submitted targets, blamed targets, and execution status into role turn results.

- The realization terminates active child processes when execution limits are exceeded.
