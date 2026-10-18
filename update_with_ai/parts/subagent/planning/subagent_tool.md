<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-18T01:30:00Z
CHANGE: support optional target unit boundary in orchestrate command
CODE_HASH: 8b8a27d23b01
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->

# subagent_tool interface component

## Intent

Multi-agent coordination requires command-line entrypoints for triggering dynamic supervision, configuring harness adapters, specifying model overrides, tuning batch sizes, setting timeout limits, and displaying convergence summaries. The subagent_tool interface component defines structured command execution contracts and result formulations for subagent orchestration.

## Factored Contracts

### Typing

- A subagent tool runner operates within the agent session lifecycle tier as a singleton service.

### Contracts

- The subagent tool runner dispatches CLI arguments for orchestration subcommands and executes the selected action. [dispatch_subagent_subcommand]
- The subagent tool runner coordinates multi-agent workspace orchestration up to an optional target role boundary and optional target unit boundary through a designated harness adapter with configurable batch sizes, execution timeouts, conversation token limits, and maximum unproductive turn limits until DAG convergence or failure. [execute_orchestrate_command]

### Woven Contracts

- When orchestrating convergence, the tool runner dispatches CLI options, delegates dynamic queue-driven supervision to the coordinator, and prints summary telemetry. [dispatch_subagent_subcommand, execute_orchestrate_command]

## Grounding

### Knowledge Provisions

- Subagent orchestration CLI execution and command dispatch services. [subagent_tool_runner_service]

### Knowledge Requirements

- Agent session lifecycle phase and context management.
  - Grounded: [session: [agent_session_tier_provision]]
