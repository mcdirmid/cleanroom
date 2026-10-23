# antigravity_harness_impl implementation component

imports: session, antigravity_ext, antigravity_harness, subagent_coordinator, subagent_harness
implements: antigravity_harness

## Purpose

The antigravity_harness_impl implementation component realizes subagent turn execution, JSONL transcript telemetry parsing, and Gemini rate-card cost calculation for Google Antigravity.

Harvesting accurate token telemetry from local execution logs and managing subprocess lifecycles requires specialized parsing and cost calculation algorithms. The antigravity_harness_impl implementation component provides transcript parsing, subprocess management, and standardized financial rate cards.

**Out of scope:** The antigravity_harness_impl implementation component does not schedule multi-wave DAG queues or generate coordinator skills; these are handled by other components.

**Delegated:** Session lifecycle scoping is delegated to agent_session; log format schemas are delegated to antigravity_ext; interface definitions are delegated to antigravity_harness; role dispatch contracts and turn result types are delegated to subagent_coordinator; platform harness registration is delegated to subagent_harness.

## Types and Behavior

The antigravity harness manager realization manages Antigravity execution adapters and transcript parsing services, and installs the Antigravity adapter factory into the harness registry.

When executing a role turn:

- The realization spawns the Antigravity subagent process bound to the role workspace directory.

- The realization polls running child processes non-blockingly to determine turn completion.

- The realization parses JSONL event lines or extracts token metric patterns from raw transcript lines to determine model token usage.

- The realization computes monetary costs using standard rate cards for Gemini Flash and Gemini Pro models.

- The realization collects submitted targets (extracting submission completion tags from process standard output), blamed targets from blame buffers, and execution status into role turn results.

- The realization terminates active child processes when execution limits are exceeded.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-13T19:15:00Z
CHANGE: support non-blocking child process polling in antigravity harness realization
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->
