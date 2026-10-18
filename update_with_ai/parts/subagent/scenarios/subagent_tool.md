<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-18T01:30:00Z
CHANGE: add scenario for bounding orchestration to target unit
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

## Scenario 4 — Configuring batch size, execution timeout, context token, and unproductive turn limits

Given: scope_a has unblocked roles and ready work targets.

1. The caller runs the orchestrate command specifying `--batch-size 3`, `--timeout 1200`, `--max-context-tokens 100000`, and `--max-unproductive-turns 8`.
   Observed: the coordinator and harness adapter receive the configured batch size, timeout, context compaction, and unproductive turn limits.

## Scenario 5 — Bounding orchestration to a target unit

Given: scope_a has multiple dirty units across different packages.

1. The caller runs the orchestrate command specifying `--target //scope_a/parts/package_a:unit_m#qa`.
   Observed: the coordinator restricts execution to unit_m and its transitive dependencies, omitting unrelated units.
