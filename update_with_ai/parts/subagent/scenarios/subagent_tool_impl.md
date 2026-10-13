<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-12T23:37:36Z
LAST_CHANGED: 2026-10-12T21:15:08Z
CHANGE: Add subagent tool impl scenarios
CODE_HASH: 7056e57a13a8
-->

# subagent_tool_impl scenarios

### Scenario 1 — Running the orchestrate command across execution waves

Given: scope_a has unblocked roles and commissioned role workspaces.

1. The caller runs the orchestrate command for scope_a through a designated harness adapter.
   Observed: the coordinator executes topological waves until convergence, prints cumulative telemetry and financial expenditures, and returns an exit code of zero.
   Realized by: the component's orchestrate argument parsing, resolving the command harness adapter through `subagent_harness`, invoking `orchestrate` on `subagent_coordinator`, and printing summary metrics.

### Scenario 2 — Refusing an unknown subcommand

Given: the caller provides an unsupported command.

1. The caller runs the command `fly`.
   Observed: the request is rejected with non-zero exit status and usage advice.
   Realized by: the component's CLI argument parsing rejecting unknown subcommands.
