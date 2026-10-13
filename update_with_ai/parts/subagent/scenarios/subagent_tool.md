<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-12T23:37:36Z
LAST_CHANGED: 2026-10-12T21:15:07Z
CHANGE: Add subagent tool scenarios
CODE_HASH: fdf8e0f3d04c
-->

# subagent_tool scenarios

## Scenario 1 — Running the orchestrate command across execution waves

Given: scope_a has unblocked roles and commissioned role workspaces.

1. The caller runs the orchestrate command for scope_a through a designated harness adapter.
   Observed: the coordinator executes topological waves until convergence, prints cumulative telemetry and financial expenditures, and returns an exit code of zero.

## Scenario 2 — Refusing an unknown subcommand

Given: the caller provides an unsupported command.

1. The caller runs the command `fly`.
   Observed: the request is rejected with non-zero exit status and usage advice.
