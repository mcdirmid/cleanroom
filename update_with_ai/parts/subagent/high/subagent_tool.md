<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-12T21:00:00Z
CHANGE: author subagent_tool interface specification
CODE_HASH: 2d991ec35409
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->

# subagent_tool interface component

imports: session

## Purpose

The subagent_tool interface component defines operational contracts for running subagent coordination commands including multi-agent orchestration across dynamic queue-driven process supervision.

Multi-agent coordination requires command-line entrypoints for triggering dynamic supervision, configuring harness adapters, specifying model overrides, tuning batch sizes, setting timeout limits, and displaying convergence summaries. The subagent_tool interface component defines structured command execution contracts and result formulations for subagent orchestration.

**Out of scope:** The subagent_tool interface component does not directly execute subagent processes or mutate workspace files; these are handled by other components.

**Delegated:** Execution phase context boundaries are delegated to agent_session.

## Types and Behavior

An agent session's *subagent tool runner* provides command dispatch and execution for subagent orchestration.

The subagent tool runner dispatches and executes orchestration commands matching an argument sequence (prepending the orchestrate command when omitted), returning an integer exit code. A module entrypoint executes command dispatch within an agent session phase.

The subagent tool runner orchestrates multi-agent execution across dynamic queue-driven process supervision for a directory scope and optional target role boundary through a designated harness adapter with configurable batch sizes, execution timeouts, conversation token limits, and maximum unproductive turn limits until DAG convergence or failure, rendering cumulative telemetry and financial expenditures.
