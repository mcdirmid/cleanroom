<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T01:05:05Z
LAST_CHANGED: 2026-10-12T21:15:03Z
CHANGE: Add subagent coordinator scenarios
CODE_HASH: 3c6bef81f8c2
-->

# subagent_coordinator scenarios

## Scenario 1 — Partitioning dirty roles into topological execution waves

Given: scope_a has dirty roles across specification and implementation levels.

1. The coordinator evaluates work queues and computes waves.
   Observed: dirty roles with unsatisfied prerequisites wait, while unblocked roles are scheduled in the first wave.

## Scenario 2 — Separating specification roles into single-role waves

Given: scope_a has multiple dirty specification roles without stub dependencies.

1. The coordinator computes waves.
   Observed: each specification role is partitioned into its own single-role wave to execute sequentially.

## Scenario 3 — Grouping independent implementation roles into parallel waves

Given: scope_a has unblocked implementation roles declaring stub role dependencies.

1. The coordinator computes waves.
   Observed: unblocked implementation roles are clustered together into a parallel execution wave.

## Scenario 4 — Iterative wave execution until DAG convergence

Given: scope_a has dirty units across roles.

1. The coordinator runs multi-wave orchestration through the harness.
   Observed: waves execute iteratively until all units evaluate clean, returning a converged summary.

## Scenario 5 — Early termination upon role failure

Given: a subagent turn in an execution wave reports failure.

1. The coordinator runs orchestration.
   Observed: execution terminates early and returns a non-converged summary with failure diagnostics.

## Scenario 6 — Cumulative token telemetry aggregation

Given: multiple subagents complete turns consuming tokens.

1. The coordinator completes an execution wave.
   Observed: total input, cached, and output tokens are aggregated into cumulative financial costs.
