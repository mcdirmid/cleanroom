<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-12T23:37:36Z
LAST_CHANGED: 2026-10-12T21:00:00Z
CHANGE: author subagent_tool interface specification
CODE_HASH: 89a9b46b4009
SPEC_QA_AUDIT: 2026-10-12T23:37:36Z
-->

# subagent_tool interface component

imports: agent_session

## Purpose

The subagent_tool interface component defines operational contracts for running subagent coordination commands including multi-agent orchestration across topological waves.

Multi-agent coordination requires command-line entrypoints for triggering wave dispatch, configuring harness adapters, specifying model overrides, and displaying convergence summaries. The subagent_tool interface component defines structured command execution contracts and result formulations for subagent orchestration.

**Out of scope:** The subagent_tool interface component does not directly execute subagent processes or mutate workspace files; these are handled by other components.

**Delegated:** Execution phase context boundaries are delegated to agent_session.

## Types and Behavior

An agent session's *subagent tool runner* provides command dispatch and execution for subagent orchestration.

The subagent tool runner dispatches and executes orchestration commands matching an argument sequence, returning an integer exit code.

The subagent tool runner orchestrates multi-agent execution across topological execution waves for a directory scope through a designated harness adapter until DAG convergence or failure, rendering cumulative telemetry and financial expenditures.
