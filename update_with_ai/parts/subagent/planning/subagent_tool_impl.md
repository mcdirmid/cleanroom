<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-12T23:37:36Z
LAST_CHANGED: 2026-10-12T21:00:00Z
CHANGE: author subagent_tool_impl planning specification
CODE_HASH: 34743d44b2e1
SPEC_QA_AUDIT: 2026-10-12T23:37:36Z
-->

# subagent_tool_impl implementation component

## Intent

Multi-agent coordination requires command-line entrypoints for triggering wave dispatch, configuring harness adapters, specifying model overrides, and displaying convergence summaries. The subagent_tool_impl implementation component defines structured command execution contracts and result formulations for subagent orchestration.

## Factored Contracts

### Typing

- The subagent tool runner realization implements SubagentToolRunner and operates in agent_session.

### Contracts

- The realization constructs argument parsers for the orchestrate command. [construct_orchestrate_cli_parser]
- In orchestrate, the runner resolves the command harness adapter, coordinates iterative wave execution via the coordinator, and renders summary metrics. [realize_orchestrate]

### Woven Contracts

- When running orchestrate, the runner resolves the harness adapter through subagent_harness, invokes coordinator orchestration across execution waves, and prints convergence telemetry. [construct_orchestrate_cli_parser, realize_orchestrate, subagent_coordinator: [orchestrate_pipeline_convergence], subagent_harness: [resolve_platform_harness_adapter], subagent_tool: [dispatch_subagent_subcommand, execute_orchestrate_command]]

## Grounding

### Knowledge Provisions

- Subagent orchestration CLI entrypoint execution implementation. [subagent_tool_runner_realization]

### Knowledge Requirements

- Multi-agent workspace coordination services.
  - Grounded: [subagent_coordinator: [subagent_coordinator_service]]
- Process harness adapter resolution services.
  - Grounded: [subagent_harness: [harness_resolver_service]]
