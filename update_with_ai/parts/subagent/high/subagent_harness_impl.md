<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T01:05:05Z
LAST_CHANGED: 2026-10-12T21:00:00Z
CHANGE: author subagent_harness_impl implementation specification
CODE_HASH: 8c46b38a177c
SPEC_QA_AUDIT: 2026-10-13T01:05:05Z
-->

# subagent_harness_impl implementation component

imports: agent_session, subagent_coordinator, subagent_harness
implements: subagent_harness

## Purpose

The subagent_harness_impl implementation component realizes the command harness adapter and harness resolution services for executing external subagent processes across isolated role workspaces.

Multi-agent coordination requires dispatching autonomous agents into isolated role workspaces, instructing them with role directives, awaiting turn completion, and extracting outcome telemetry without coupling the central scheduler to platform-specific SDKs. Without a generalized process harness contract, each agent platform requires bespoke process management, inconsistent prompt formulation, and duplicate buffer inspection. The subagent_harness_impl implementation component formalizes command template execution, structured role prompt formulation, workspace pending and blame buffer inspection, process lifecycle control, and turn result synthesis.

**Out of scope:** The subagent_harness_impl implementation component does not compute topological waves or evaluate DAG dirtiness; these are handled by other components.

**Delegated:** Session lifecycle scoping is delegated to agent_session; coordinator dispatch and turn outcome data types are delegated to subagent_coordinator.

## Types and Behavior

The command harness adapter realization executes subagent processes, formats task instructions, monitors workspace buffers, and synthesizes turn results.

When realizing subagent dispatch and outcome monitoring:

- The realization constructs instructional task prompts detailing role responsibilities, workspace context, ready targets, check-files verification commands, and role tool submission and blame workflows.

- The realization captures initial pending targets from the workspace pending work buffer prior to process execution.

- The realization interpolates command templates with workspace directory, role name, and task prompt variables, spawning subprocesses within the target workspace directory and recording active process handles.

- The realization awaits subprocess termination bounded by configured timeout limits, killing delinquent processes upon timeout, reading blame records from the workspace blame buffer, determining submitted targets by set difference with remaining pending items, parsing token metrics from process log files, and computing financial costs.

- The realization returns role turn results reflecting clean execution, blamed feedback, or process failures with captured error diagnostics.

- The harness resolver realization maps platform names including Antigravity, Goose, and DeepSeek Harness to canonical CLI command templates, or enables simulation mode for testing.
