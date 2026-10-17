<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-13T12:00:00Z
CHANGE: update subagent tool impl scenarios for dynamic supervision and options
CODE_HASH: 7059c6ce17f1
-->

# subagent_tool_impl scenarios

### Scenario 1 — Running the orchestrate command via dynamic queue supervision

Given: scope_a has unblocked roles and ready work targets.

1. The caller runs the orchestrate command for scope_a through a designated harness adapter.
   Observed: the coordinator executes dynamic queue-driven supervision until convergence, prints cumulative telemetry and financial expenditures, and returns an exit code of zero.
   Realized by: the component's orchestrate argument parsing, resolving the command harness adapter through `subagent_harness`, invoking `orchestrate` on `subagent_coordinator`, and printing summary metrics.

### Scenario 2 — Refusing an unknown subcommand

Given: the caller provides an unsupported command.

1. The caller runs the command `fly`.
   Observed: the request is rejected with non-zero exit status and usage advice.
   Realized by: the component's CLI argument parsing rejecting unknown subcommands.

### Scenario 3 — Bounding orchestration to a target role

Given: scope_a has unblocked roles across multiple development stages.

1. The caller runs the orchestrate command specifying a target role.
   Observed: the coordinator executes supervision only up to the target role, ignoring downstream stages.
   Realized by: the component's orchestrate CLI parsing extracting the target role argument and passing it to the coordinator.

### Scenario 4 — Configuring batch size, execution timeout, context token, and unproductive turn limits

Given: scope_a has unblocked roles and ready work targets.

1. The caller runs the orchestrate command specifying `--batch-size 3`, `--timeout 1200`, `--max-context-tokens 100000`, and `--max-unproductive-turns 8`.
   Observed: the coordinator and harness adapter receive the configured batch size, timeout, context compaction, and unproductive turn limits.
   Realized by: the component's CLI options parsing `--batch-size`, `--timeout`, `--max-context-tokens`, and `--max-unproductive-turns` and propagating them to harness resolution and coordinator options.
