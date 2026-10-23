# subagent_harness interface component

imports: session, subagent_coordinator

## Purpose

The subagent_harness interface component defines contracts for process-based subagent execution harnesses and platform harness registries driving role rounds across external AI platforms.

Multi-agent coordination requires dispatching autonomous agents into isolated role workspaces, instructing them with role directives, awaiting round completion, and extracting outcome telemetry without coupling the central scheduler to platform-specific SDKs. Without a generalized process harness contract, each agent platform requires bespoke process management, inconsistent prompt formulation, and duplicate buffer inspection. The subagent_harness interface component formalizes command template execution, structured role prompt formulation, workspace pending and blame buffer inspection, process lifecycle control, and round result synthesis.

**Out of scope:** The subagent_harness interface component does not compute topological waves or evaluate DAG dirtiness; these are handled by other components.

**Delegated:** Session lifecycle scoping is delegated to agent_session; coordinator dispatch and round outcome data types are delegated to subagent_coordinator.

## Types and Behavior

A *command harness adapter* implements the coordinator harness adapter protocol to execute role subagent rounds through configurable process command templates.

When dispatching and awaiting role rounds:

- The command harness adapter formats instructional task prompts detailing the active role, directory scope, assigned targets, guide compliance expectations, verification commands, and submission or blame actions.

- The command harness adapter records initial pending targets from the workspace pending work buffer prior to process execution.

- The command harness adapter spawns external subagent processes matching configured command templates within the designated role workspace directory, configuring context token compaction limits in the process environment, and tracking active task handles.

- The command harness adapter provides non-blocking polling and awaiting of process completion without mandatory execution timeouts, terminating stalled processes only when an explicit timeout limit is configured, inspecting the workspace blame buffer for attributed defects, checking remaining pending targets to identify submitted files, and extracting token usage telemetry from execution logs (parsing token metrics via pattern matching on unstructured process logs and computing monetary costs using standard rate multipliers, and on non-zero process exits inspecting the tail of the process log for failure diagnostics).

- The command harness adapter produces role round results carrying round status (clean, blamed, or failed), submitted target sequences, blamed target sequences, failure diagnostics, token usage telemetry, and elapsed wall-clock duration.

- An *adapter factory* creates harness adapters configured with model name, timeout, context limits, custom command templates, or simulation mode.

- An agent session's *harness registry* maintains installed adapter factories by platform name, installs platform adapter factories, and resolves harness adapters for designated platform names, custom command templates, or simulation mode.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-20T10:00:00Z
CHANGE: Standardize terminology on role rounds and role round results, deprecating turn terminology
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->
