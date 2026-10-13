<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T20:42:16Z
LAST_CHANGED: 2026-10-13T09:50:00Z
CHANGE: author goose_harness_impl implementation specification
CODE_HASH: a7e9e2c61d36
SPEC_QA_AUDIT: 2026-10-13T20:42:16Z
-->

# goose_harness_impl implementation component

imports: agent_session, goose_ext, subagent_coordinator, workspace_work
implements: goose_harness

## Purpose

The goose_harness_impl implementation component realizes Goose subagent turn execution, process lifecycle control, and SQLite session telemetry harvesting.

Operating Goose within Cleanroom requires concrete process dispatch via the Goose CLI, active turn supervision, SQLite database inspection, and standard rate-card calculations. Without concrete process and database integration, Goose turns cannot be invoked headlessly or evaluated for token cost. The goose_harness_impl implementation component realizes the harness adapter and telemetry parser contracts for production Goose execution.

**Out of scope:** The goose_harness_impl implementation component does not partition topological waves or evaluate DAG dirtiness; these are handled by other components.

**Delegated:** Session lifecycle scoping is delegated to agent_session; platform conventions are delegated to goose_ext; harness adapter protocols and turn outcome types are delegated to subagent_coordinator; workspace work queue querying is delegated to workspace_work.

## Types and Behavior

The goose telemetry parser queries the Goose SQLite session database and parses execution logs to extract token metrics.

When parsing session telemetry:

- The goose telemetry parser queries the sessions database to retrieve recorded input tokens, output tokens, and cache read tokens for the target session identifier or working directory.

- The goose telemetry parser applies pricing rates for the active model family to compute total monetary expenditure in USD.

- The goose telemetry parser parses text log streams as fallback when database records are unavailable.

The goose harness adapter executes Goose turns using configurable command lines within target role workspaces.

When dispatching and awaiting role turns:

- The goose harness adapter writes task prompts to disk and records initial pending targets before launching the Goose process.

- The goose harness adapter launches the Goose CLI in the role workspace directory, setting context token compaction environment variables, and tracks running process handles.

- The goose harness adapter polls and awaits process termination without mandatory execution timeouts, terminating active processes only when an explicit timeout duration expires.

- The goose harness adapter inspects workspace blame buffers, computes submitted targets by comparing pending work buffers, and parses token metrics into normalized telemetry.

The goose harness manager provides singleton access to the telemetry parser and constructs configured Goose harness adapters.
