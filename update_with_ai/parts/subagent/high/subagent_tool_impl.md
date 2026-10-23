# subagent_tool_impl implementation component

imports: session, subagent_coordinator, subagent_harness, subagent_tool
implements: subagent_tool

## Purpose

The subagent_tool_impl implementation component realizes the subagent tool runner for CLI command parsing and multi-agent orchestration execution.

Multi-agent coordination requires command-line entrypoints for triggering wave dispatch, configuring harness adapters, specifying model overrides, and displaying convergence summaries. The subagent_tool_impl implementation component defines structured command execution contracts and result formulations for subagent orchestration.

**Out of scope:** The subagent_tool_impl implementation component does not directly execute subagent processes or mutate workspace files; these are handled by other components.

**Delegated:** Execution phase context boundaries are delegated to agent_session; multi-agent pipeline orchestration is delegated to subagent_coordinator; command harness resolution is delegated to subagent_harness.

## Types and Behavior

The subagent tool runner realization implements command execution, command-line argument parsing, and diagnostic formatting for subagent orchestration.

The realization parses command-line arguments, prepending the default orchestrate subcommand when omitted from arguments, including directory scope, optional target role boundary, optional target unit boundary, harness platform, model identifier, maximum waves, batch size constraints, execution timeout limits, conversation token limits, and maximum unproductive round limits. A module entrypoint runs the tool runner within an agent session phase.

The realization resolves the execution harness adapter through the harness resolver with configured timeout and token limits, dispatches dynamic supervision with optional unproductive round limits to the coordinator until convergence, and prints execution metrics.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-20T10:00:00Z
CHANGE: Standardize terminology on unproductive round limits, deprecating turn terminology
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->
