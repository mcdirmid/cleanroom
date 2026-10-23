# subagent_coordinator_impl scenarios

### Scenario 1 — Resetting preexisting role workspaces on startup

Given: role workspaces for scope_a already exist from a previous run.

1. The coordinator initiates orchestration.
   Observed: preexisting role workspace directories for declared roles in scope_a are removed to establish a clean initial state.
   Realized by: the component's workspace reset routine deleting existing workspace directories for declared roles before queue evaluation.

### Scenario 2 — Dynamically identifying unblocked roles with available work

Given: scope_a has dirty roles across multiple levels where some roles have unsatisfied prerequisites.

1. The coordinator evaluates work queues for all roles.
   Observed: roles with blocked prerequisites report empty queues, while unblocked roles with ready targets are identified for execution.
   Realized by: the component's dynamic queue query querying `work` across declared roles without hardcoded topology logic.

### Scenario 3 — Dispatching concurrent worker processes for unblocked roles

Given: scope_a has unblocked roles role_a and role_b each with available work targets and no active workers.

1. The coordinator dispatches workers.
   Observed: role workspaces are provisioned and concurrent subagent processes are launched for role_a and role_b simultaneously.
   Realized by: the component's concurrent worker dispatch commissioning workspaces via `provision` and invoking `spawn_role` on `subagent_harness`.

### Scenario 4 — Continuous non-blocking polling and dynamic supervisor loop

Given: active workers are executing in background processes for role_a and role_b.

1. The coordinator polls active workers.
   Observed: completed workers are reaped without blocking while running workers continue execution unhindered.
   Realized by: the component's supervisor loop calling `poll_role` on `subagent_harness` and sleeping between poll cycles at the configured polling interval (defaulting to 10 seconds).

### Scenario 5 — Restarting role workers when new unblocked work emerges

Given: role_a completes and submits changes that unblock ready targets in downstream role_c.

1. The coordinator continues dynamic supervision.
   Observed: the coordinator provisions role_c workspace and launches a worker process for role_c.
   Realized by: the component's continuous loop re-evaluating `work.compute_role_work_queue` and launching workers for newly unblocked roles.

### Scenario 6 — Early termination upon role worker failure

Given: an active subagent worker process for role_a fails or exits with an unresolvable error.

1. The coordinator polls active workers.
   Observed: dynamic supervision halts and returns a non-converged summary with failure diagnostics.
   Realized by: the component's error handler detecting failed round status and breaking the supervisor loop.

### Scenario 7 — Cumulative token telemetry aggregation

Given: multiple concurrent subagent rounds complete consuming tokens.

1. The coordinator reaps finished worker rounds.
   Observed: input, cached, and output tokens from all completed rounds are aggregated into cumulative financial costs.
   Realized by: the component's telemetry accumulator aggregating round token usages into cumulative project totals.

### Scenario 8 — Restricting execution up to a target role boundary

Given: scope_a has dirty roles across specification and implementation levels.

1. The coordinator inspects work queues bounded by a target role.
   Observed: only roles up to the target role boundary are evaluated and scheduled; downstream roles are excluded.
   Realized by: the component's role filtering slicing declared roles up to the matching target role.

### Scenario 9 — Deleting provisioned role workspaces upon clean convergence

Given: dynamic supervision achieves clean convergence across all evaluated roles in scope_a.

1. The coordinator concludes orchestration.
   Observed: all provisioned role workspace directories for scope_a are automatically deleted before returning the summary.
   Realized by: the component's convergence cleanup deleting all provisioned role workspace directories for scope_a when is_converged is true.

### Scenario 10 — Halting orchestration upon consecutive unproductive round impasse

Given: role_a completes consecutive execution rounds without submitting or blaming any ready targets and its assigned ready targets remain unresolved in the repository.

1. The coordinator polls active workers.
   Observed: dynamic supervision halts when unproductive rounds on unresolved targets reach the threshold, returning a non-converged summary with impasse details; unproductive round counts and scolding reminders are suppressed when assigned ready targets are resolved or cleaned in the repository.
   Realized by: the component's impasse detection tracking consecutive rounds yielding zero submitted and zero blamed targets on unresolved targets and breaking the supervisor loop.

### Scenario 11 — Decommissioning workspaces and interrupting workers on cancellation

Given: active workers are executing in provisioned workspaces for scope_a when a cancellation signal occurs.

1. The coordinator receives a cancellation signal during dynamic supervision.
   Observed: all running workers are interrupted through the harness adapter and all provisioned role workspace directories for scope_a are deleted.
   Realized by: the component's cancellation handler catching cancellation, calling `interrupt_role` on active worker handles, and deleting provisioned role workspace directories for scope_a.

### Scenario 12 — Reminding role workers upon unresolved round completion

Given: a role worker completes a round without submitting, blaming, or failing assigned ready targets and its assigned ready targets remain unresolved in the repository.

1. The coordinator reaps the unresolved round and dispatches a subsequent round for the role.
   Observed: the subsequent role dispatch directive includes an actionable reminder in its task prompt instructing the worker to verify with check_files and conclude the round via submit, blame, or fail without conversational stopping; reminders are suppressed when assigned ready targets were resolved or cleaned in the repository.
   Realized by: the component's unresolved round tracker recording a reminder string upon observing zero submitted and zero blamed targets on unresolved targets without failure, and setting task_prompt on the next RoleDispatch.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-20T23:45:00Z
CHANGE: Suppress unproductive rounds and scolding reminders when assigned targets are resolved or cleaned in the repository
-->
