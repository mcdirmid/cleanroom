<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-12T23:37:36Z
LAST_CHANGED: 2026-10-12T21:15:06Z
CHANGE: Add subagent coordinator impl scenarios
CODE_HASH: 749c3b779a40
-->

# subagent_coordinator_impl scenarios

### Scenario 1 — Partitioning dirty roles into topological execution waves

Given: scope_a has dirty roles across specification and implementation levels.

1. The coordinator evaluates work queues and computes waves.
   Observed: dirty roles with unsatisfied prerequisites wait, while unblocked roles are scheduled in the first wave.
   Realized by: the component's topological wave discovery querying `workspace_registry` and `workspace_work`.

### Scenario 2 — Separating specification roles into single-role waves

Given: scope_a has multiple dirty specification roles without stub dependencies.

1. The coordinator computes waves.
   Observed: each specification role is partitioned into its own single-role wave to execute sequentially.
   Realized by: the component's wave partitioning isolating roles that do not declare stub dependencies.

### Scenario 3 — Grouping independent implementation roles into parallel waves

Given: scope_a has unblocked implementation roles declaring stub role dependencies.

1. The coordinator computes waves.
   Observed: unblocked implementation roles are clustered together into a parallel execution wave.
   Realized by: the component's wave partitioning clustering unblocked implementation roles with stub dependencies into parallel waves.

### Scenario 4 — Iterative wave execution until DAG convergence

Given: scope_a has dirty units across roles.

1. The coordinator runs multi-wave orchestration through the harness.
   Observed: waves execute iteratively until all units evaluate clean, returning a converged summary.
   Realized by: the component's convergence loop iteratively running waves until work queues empty.

### Scenario 5 — Early termination upon role failure

Given: a subagent turn in an execution wave reports failure.

1. The coordinator runs orchestration.
   Observed: execution terminates early and returns a non-converged summary with failure diagnostics.
   Realized by: the component's error handling breaking the wave loop upon non-zero exit or failure status.

### Scenario 6 — Cumulative token telemetry aggregation

Given: multiple subagents complete turns consuming tokens.

1. The coordinator completes an execution wave.
   Observed: total input, cached, and output tokens are aggregated into cumulative financial costs.
   Realized by: the component's rate card pricing calculation tallying turn token usages.

### Scenario 7 — Auto-commissioning absent role workspaces before dispatch

Given: scope_a has an unblocked dirty role whose workspace directory has not yet been provisioned.

1. The coordinator computes waves.
   Observed: the coordinator detects the absent workspace directory and commissions it via `workspace_provision` before constructing the role dispatch.
   Realized by: the component's absent workspace check delegating to `workspace_provision.WorkspaceProvisioner.commission`.
