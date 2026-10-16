<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:47Z
LAST_CHANGED: 2026-10-14T17:50:00Z
CHANGE: Delegate substantive command workflows to workspace_commands
CODE_HASH: f912594c7be7
SPEC_QA_AUDIT: 2026-10-15T17:42:47Z
-->

# workspace_tool_impl implementation component

imports: agent_session, workspace_commands
implements: workspace_tool

## Purpose

The workspace_tool_impl implementation component realizes the workspace tool runner for cleanroom role workspace CLI entrypoint and argument parsing.

Command-line subagents in Cleanroom workspaces require a robust entrypoint that parses subcommands, options, and arguments, presenting formatted help and dispatching commands cleanly to operational handlers. The workspace_tool_impl implementation component consolidates argument parsing, command dispatch tables, and return code normalization into a singleton runner operating within the agent session lifecycle tier.

**Out of scope:** The workspace_tool_impl implementation component does not directly implement filesystem synchronization, submission validation, or coverage analysis; these are delegated to workspace_commands.

**Delegated:** Session tier scoping is delegated to agent_session; substantive command workflows are delegated to workspace_commands.

## Types and Behavior

The workspace tool runner realization implements command-line argument parsing and command dispatch.

The realization:

- Builds argument parsers and dispatches command execution across the work, check files, submit, blame, feedback, fail, coverage, commission, and refresh system subcommands, supporting repository root overrides for blame, fail, and coverage, and delegating execution to the workspace command handler.

- Normalizes integer exit codes and error handling across dispatched commands, guaranteeing execution operates within the agent session lifecycle tier.
