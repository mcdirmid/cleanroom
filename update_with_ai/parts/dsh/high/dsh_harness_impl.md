<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T20:42:16Z
LAST_CHANGED: 2026-10-13T20:00:00Z
CHANGE: author dsh_harness_impl implementation specification
CODE_HASH: 65f6e2f13858
SPEC_QA_AUDIT: 2026-10-13T20:42:16Z
-->

# dsh_harness_impl implementation component

imports: agent_session, dsh_ext, subagent_coordinator, workspace_work
implements: dsh_harness

## Purpose

The dsh_harness_impl implementation component realizes DeepSeek Harness subagent turn execution, process lifecycle control, and event stream / session storage telemetry harvesting.

Operating DeepSeek Harness within Cleanroom requires concrete process dispatch via the dsh CLI headless profile, active turn supervision, event stream inspection, and standard rate-card calculations. Without concrete process and telemetry integration, DeepSeek Harness turns cannot be invoked headlessly or evaluated for token cost. The dsh_harness_impl implementation component realizes the harness adapter and telemetry parser contracts for production DeepSeek Harness execution.

**Out of scope:** The dsh_harness_impl implementation component does not partition topological waves or evaluate DAG dirtiness; these are handled by other components.

**Delegated:** Session lifecycle scoping is delegated to agent_session; platform conventions are delegated to dsh_ext; harness adapter protocols and turn outcome types are delegated to subagent_coordinator; workspace work queue querying is delegated to workspace_work.

## Types and Behavior

The dsh telemetry parser inspects DeepSeek Harness event streams and session storage archives to extract token metrics.

When parsing session telemetry:

- The dsh telemetry parser parses JSON stream events or queries session storage archives to retrieve recorded input tokens, output tokens, and cache read tokens.

- The dsh telemetry parser applies pricing rates for the active model family to compute total monetary expenditure in USD.

- The dsh telemetry parser parses text log streams as fallback when structured records are unavailable.

The dsh harness adapter executes DeepSeek Harness turns using configurable command lines within target role workspaces.

When dispatching and awaiting role turns:

- The dsh harness adapter writes task prompts to disk and records initial pending targets before launching the DeepSeek Harness process.

- The dsh harness adapter launches the dsh CLI in the role workspace directory, setting overlay patch parameters and non-interactive permission flags, and tracks running process handles.

- The dsh harness adapter polls and awaits process termination without mandatory execution timeouts, terminating active processes only when an explicit timeout duration expires.

- The dsh harness adapter inspects workspace blame buffers, computes submitted targets by comparing pending work buffers, and parses token metrics into normalized telemetry.

The dsh harness manager provides singleton access to the telemetry parser and constructs configured DeepSeek Harness adapters.
