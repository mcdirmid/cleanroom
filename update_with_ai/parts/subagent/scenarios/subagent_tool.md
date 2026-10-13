<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T20:42:15Z
LAST_CHANGED: 2026-10-13T12:00:00Z
CHANGE: update subagent tool scenarios for dynamic supervision and options
CODE_HASH: 506f34fa28ba
-->

# subagent_tool scenarios

## Scenario 1 — Running the orchestrate command via dynamic queue supervision

Given: scope_a has unblocked roles and ready work targets.

1. The caller runs the orchestrate command for scope_a through a designated harness adapter.
   Observed: the coordinator executes dynamic queue-driven supervision until convergence, prints cumulative telemetry and financial expenditures, and returns an exit code of zero.

## Scenario 2 — Refusing an unknown subcommand

Given: the caller provides an unsupported command.

1. The caller runs the command `fly`.
   Observed: the request is rejected with non-zero exit status and usage advice.

## Scenario 3 — Bounding orchestration to a target role

Given: scope_a has unblocked roles across multiple development stages.

1. The caller runs the orchestrate command specifying a target role.
   Observed: the coordinator executes supervision only up to the target role, ignoring downstream stages.

## Scenario 4 — Configuring batch size, execution timeout, and context token limits

Given: scope_a has unblocked roles and ready work targets.

1. The caller runs the orchestrate command specifying `--batch-size 3`, `--timeout 1200`, and `--max-context-tokens 100000`.
   Observed: the coordinator and harness adapter receive the configured batch size, timeout, and context compaction limits.
