<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T19:43:57Z
LAST_CHANGED: 2026-10-12T21:00:00Z
CHANGE: author subagent_asm assembly specification
CODE_HASH: 042fb0a44213
SPEC_QA_AUDIT: 2026-10-15T19:43:57Z
-->

# subagent_asm assembly component

assembles: subagent_coordinator_impl, subagent_harness_impl, subagent_tool_impl
imports: agent_session
implements: subagent_coordinator, subagent_harness, subagent_tool

## Purpose

The subagent_asm assembly component aggregates constituent subagent execution and coordination implementation components, exposing complete subagent orchestration services.

Multi-agent operations require coordinated wiring of wave scheduling, process harness execution, and CLI orchestration. The subagent_asm assembly component closes subagent interfaces and assembles all constituent implementation components into a unified assembly.

**Out of scope:** The subagent_asm assembly component does not define custom business logic, dispatch agent requests, or drive pipeline execution; these are handled by other components.

## Types and Behavior

The subagent_asm assembly component aggregates the implementations of the subagent coordinator, subagent harness, and subagent tool interfaces, providing a unified assembly for subagent execution and multi-agent coordination.

The subagent assembly initializes its constituent implementations recursively and registers every singleton service with the agent session lifecycle tier.
