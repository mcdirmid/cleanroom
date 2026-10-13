<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T01:05:05Z
LAST_CHANGED: 2026-10-12T21:00:00Z
CHANGE: author subagent_harness interface specification
CODE_HASH: 11c2ffb831a6
SPEC_QA_AUDIT: 2026-10-13T01:05:05Z
-->

# subagent_harness interface component

imports: agent_session, subagent_coordinator

## Purpose

The subagent_harness interface component defines contracts for process-based subagent execution harnesses driving role turns across external AI platforms such as Antigravity, Goose, and DeepSeek Harness.

Multi-agent coordination requires dispatching autonomous agents into isolated role workspaces, instructing them with role directives, awaiting turn completion, and extracting outcome telemetry without coupling the central scheduler to platform-specific SDKs. Without a generalized process harness contract, each agent platform requires bespoke process management, inconsistent prompt formulation, and duplicate buffer inspection. The subagent_harness interface component formalizes command template execution, structured role prompt formulation, workspace pending and blame buffer inspection, process lifecycle control, and turn result synthesis.

**Out of scope:** The subagent_harness interface component does not compute topological waves or evaluate DAG dirtiness; these are handled by other components.

**Delegated:** Session lifecycle scoping is delegated to agent_session; coordinator dispatch and turn outcome data types are delegated to subagent_coordinator.

## Types and Behavior

A *command harness adapter* implements the coordinator harness adapter protocol to execute role subagent turns through configurable process command templates.

When dispatching and awaiting role turns:

- The command harness adapter formats instructional task prompts detailing the active role, directory scope, assigned targets, guide compliance expectations, verification commands, and submission or blame actions.

- The command harness adapter records initial pending targets from the workspace pending work buffer prior to process execution.

- The command harness adapter spawns external subagent processes matching configured command templates within the designated role workspace directory, tracking active task handles.

- The command harness adapter awaits process completion or timeout, terminates stalled processes upon timeout expiration, inspects the workspace blame buffer for attributed defects, checks remaining pending targets to identify submitted files, and extracts token usage telemetry from execution logs.

- The command harness adapter produces role turn results carrying turn status (clean, blamed, or failed), submitted target sequences, blamed target sequences, failure diagnostics, token usage telemetry, and elapsed wall-clock duration.

- A *harness resolver* resolves platform command templates for designated harness platforms including Antigravity, Goose, and DeepSeek Harness, or produces simulation harnesses when simulation mode is active.
