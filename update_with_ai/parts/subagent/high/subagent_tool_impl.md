<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-12T21:00:00Z
CHANGE: author subagent_tool_impl implementation specification
CODE_HASH: 93fb466020ff
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->

# subagent_tool_impl implementation component

imports: agent_session, subagent_coordinator, subagent_harness, subagent_tool
implements: subagent_tool

## Purpose

The subagent_tool_impl implementation component realizes the subagent tool runner for CLI command parsing and multi-agent orchestration execution.

Multi-agent coordination requires command-line entrypoints for triggering wave dispatch, configuring harness adapters, specifying model overrides, and displaying convergence summaries. The subagent_tool_impl implementation component defines structured command execution contracts and result formulations for subagent orchestration.

**Out of scope:** The subagent_tool_impl implementation component does not directly execute subagent processes or mutate workspace files; these are handled by other components.

**Delegated:** Execution phase context boundaries are delegated to agent_session; multi-agent pipeline orchestration is delegated to subagent_coordinator; command harness resolution is delegated to subagent_harness.

## Types and Behavior

The subagent tool runner realization implements command execution, command-line argument parsing, and diagnostic formatting for subagent orchestration.

The realization parses command-line arguments for the orchestrate command, including directory scope, optional target role boundary, harness platform, model identifier, maximum waves, batch size constraints, execution timeout limits, and conversation token limits.

The realization resolves the execution harness adapter through the harness resolver with configured timeout and token limits, dispatches dynamic supervision to the coordinator until convergence, and prints execution metrics.
