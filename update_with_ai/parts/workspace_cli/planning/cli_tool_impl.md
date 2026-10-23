# cli_tool_impl implementation component

## Intent

Command-line subagents in Cleanroom workspaces require a robust entrypoint that parses subcommands, options, and arguments, presenting formatted help and dispatching commands cleanly to operational handlers. The cli_tool_impl implementation component consolidates argument parsing, command dispatch tables, and return code normalization into a singleton runner operating within the agent session lifecycle tier, delegating substantive domain workflows to the workspace command handler.

## Factored Contracts

### Typing

- The workspace tool runner realization implements WorkspaceToolRunner and operates in agent_session.

### Contracts

- The realization constructs argument parsers for commission, refresh-sys, get_work, check_files, submit, blame, feedback, fail, and coverage, supporting repository root overrides for blame, fail, and coverage. [construct_cli_parser]
- The realization parses command-line arguments and dispatches execution to the workspace command handler within the agent session lifecycle tier, normalizing exit codes. [dispatch_role_subcommand]

### Woven Contracts

- When running a role subcommand, the runner parses CLI arguments and delegates execution to the workspace command handler within the agent session lifecycle tier. [dispatch_role_subcommand, construct_cli_parser, cli_tool: [dispatch_role_subcommand], commands: [execute_get_work_command, execute_check_files_command, execute_submit_command, execute_blame_command, execute_coverage_command, execute_commission_command, execute_refresh_sys_command]]

## Grounding

### Knowledge Provisions

- Cleanroom role workspace CLI entrypoint execution implementation. [workspace_tool_realization]

### Inherited Deferred Requirements

- Dispatch and execution of role workspace commands.
  - Grounded: [workspace_tool_realization, commands: [workspace_commands_service]]

### Knowledge Requirements

- Agent session lifecycle phase and context management.
  - Grounded: [session: [agent_session_tier_provision]]
- Role workspace domain command execution workflows.
  - Grounded: [commands: [workspace_commands_service]]

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:47Z
LAST_CHANGED: 2026-10-14T17:50:00Z
CHANGE: Delegate substantive command workflows to commands
SPEC_QA_AUDIT: 2026-10-15T17:42:47Z
-->
