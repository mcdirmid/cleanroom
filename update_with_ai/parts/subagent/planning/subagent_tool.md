<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-12T23:37:36Z
LAST_CHANGED: 2026-10-12T21:00:00Z
CHANGE: author subagent_tool planning specification
CODE_HASH: 8021b2eaa78d
SPEC_QA_AUDIT: 2026-10-12T23:37:36Z
-->

# subagent_tool interface component

## Intent

Multi-agent coordination requires command-line entrypoints for triggering wave dispatch, configuring harness adapters, specifying model overrides, and displaying convergence summaries. The subagent_tool interface component defines structured command execution contracts and result formulations for subagent orchestration.

## Factored Contracts

### Typing

- A subagent tool runner operates within the agent session lifecycle tier as a singleton service.

### Contracts

- The subagent tool runner dispatches CLI arguments for orchestration subcommands and executes the selected action. [dispatch_subagent_subcommand]
- The subagent tool runner coordinates multi-agent workspace orchestration through a designated harness adapter until DAG convergence or failure. [execute_orchestrate_command]

### Woven Contracts

- When orchestrating convergence, the tool runner dispatches CLI options, delegates wave execution to the coordinator, and prints summary telemetry. [dispatch_subagent_subcommand, execute_orchestrate_command]

## Grounding

### Knowledge Provisions

- Subagent orchestration CLI execution and command dispatch services. [subagent_tool_runner_service]

### Knowledge Requirements

- Agent session lifecycle phase and context management.
  - Grounded: [agent_session: [agent_session_tier_provision]]
