# subagent_coordinator scenarios

## Scenario 1 — Resetting preexisting role workspaces on startup

Given: role workspaces for scope_a already exist from a previous run.

1. The coordinator initiates orchestration.
   Observed: preexisting role workspace directories for declared roles in scope_a are removed to establish a clean initial state.

## Scenario 2 — Dynamically identifying unblocked roles with available work

Given: scope_a has dirty roles across multiple levels where some roles have unsatisfied prerequisites.

1. The coordinator evaluates work queues for all roles.
   Observed: roles with blocked prerequisites report empty queues, while unblocked roles with ready targets are identified for execution.

## Scenario 3 — Dispatching concurrent worker processes for unblocked roles

Given: scope_a has unblocked roles role_a and role_b each with available work targets and no active workers.

1. The coordinator dispatches workers.
   Observed: role workspaces are provisioned and concurrent subagent processes are launched for role_a and role_b simultaneously.

## Scenario 4 — Continuous non-blocking polling and dynamic supervisor loop

Given: active workers are executing in background processes for role_a and role_b.

1. The coordinator polls active workers.
   Observed: completed workers are reaped without blocking while running workers continue execution unhindered.

## Scenario 5 — Restarting role workers when new unblocked work emerges

Given: role_a completes and submits changes that unblock ready targets in downstream role_c.

1. The coordinator continues dynamic supervision.
   Observed: the coordinator provisions role_c workspace and launches a worker process for role_c.

## Scenario 6 — Early termination upon role worker failure

Given: an active subagent worker process for role_a fails or exits with an unresolvable error.

1. The coordinator polls active workers.
   Observed: dynamic supervision halts and returns a non-converged summary with failure diagnostics.

## Scenario 7 — Cumulative token telemetry aggregation

Given: multiple concurrent subagent rounds complete consuming tokens.

1. The coordinator reaps finished worker rounds.
   Observed: input, cached, and output tokens from all completed rounds are aggregated into cumulative financial costs.

## Scenario 8 — Restricting execution up to a target role boundary

Given: scope_a has dirty roles across specification and implementation levels.

1. The coordinator inspects work queues bounded by a target role.
   Observed: only roles up to the target role boundary are evaluated and scheduled; downstream roles are excluded.

## Scenario 9 — Deleting provisioned role workspaces upon clean convergence

Given: dynamic supervision achieves clean convergence across all evaluated roles in scope_a.

1. The coordinator concludes orchestration.
   Observed: all provisioned role workspace directories for scope_a are automatically deleted before returning the summary.

## Scenario 10 — Restricting execution to a target unit and its transitive dependencies

Given: scope_a has dirty units unit_m and unit_n, where unit_m does not depend on unit_n.

1. The coordinator inspects work queues bounded by target unit unit_m.
   Observed: only unit_m and its transitive upstream dependencies are evaluated and scheduled; unit_n is excluded.

## Scenario 11 — Decommissioning workspaces and interrupting workers on cancellation

Given: active workers are executing in provisioned workspaces for scope_a when a cancellation signal occurs.

1. The coordinator receives a cancellation signal during dynamic supervision.
   Observed: all running workers are interrupted through the harness adapter and all provisioned role workspace directories for scope_a are deleted.

## Scenario 12 — Reminding role workers upon unresolved round completion

Given: a role worker completes a round without submitting, blaming, or failing assigned ready targets.

1. The coordinator reaps the unresolved round and dispatches a subsequent round for the role.
   Observed: the subsequent role dispatch directive includes an actionable reminder in its task prompt instructing the worker to verify with check_files and conclude the round via submit, blame, or fail without conversational stopping.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-18T01:30:00Z
CHANGE: add scenario for restricting execution to target units and transitive dependencies
-->
