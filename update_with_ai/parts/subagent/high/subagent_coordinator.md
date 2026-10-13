<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T01:05:05Z
LAST_CHANGED: 2026-10-12T21:00:00Z
CHANGE: author subagent_coordinator interface specification
CODE_HASH: d3f1a7bbf285
SPEC_QA_AUDIT: 2026-10-13T01:05:05Z
-->

# subagent_coordinator interface component

imports: agent_session

## Purpose

The subagent_coordinator interface component defines data types and operational contracts for zero-execution multi-agent workspace coordination across topological DAG waves and pluggable execution harnesses.

Complex software development methodologies partition work into specialized roles that depend on upstream artifacts. Executing these roles concurrently without ordering guarantees leads to cache thrashing, race conditions, and invalidated context. The subagent_coordinator interface component formalizes topological wave clustering, parallel and sequential execution waves, harness abstraction, turn result aggregation, blame defect propagation, and cumulative token rate-card accounting.

**Out of scope:** The subagent_coordinator interface component does not directly execute subagent processes or mutate workspace files; these are handled by other components.

**Delegated:** Session lifecycle scoping is delegated to agent_session.

## Types and Behavior

A *token usage record* tracks uncached prompt tokens, cached prompt tokens, completion tokens, total tokens, and financial expenditure in USD.

A *role dispatch directive* captures the parameters required to execute an agent turn within an isolated role workspace, including the target role name, workspace directory, directory scope, ready target paths, optional batch size bounding, and formatted instruction prompt.

A *role turn result* captures the outcome of an autonomous subagent turn, including the role identifier, outcome status (clean, blamed, or failed), sequences of submitted targets and blamed targets, optional failure diagnostics, token telemetry, and elapsed execution time.

An *orchestration summary* captures the cumulative outcome of multi-wave coordination, including convergence status, total waves executed, total units submitted, total units blamed, cumulative token usage telemetry, and diagnostic status messages.

An abstract *harness adapter* defines the execution protocol for dispatching role directives, awaiting turn results, and interrupting runaway turns.

A system's *subagent coordinator* schedules and orchestrates autonomous subagents across role workspaces within an agent session.

When coordinating multi-agent execution:

- The subagent coordinator evaluates DAG work queues and partitions unblocked dirty roles into topological execution waves.

- The subagent coordinator ensures absent role workspaces are commissioned via workspace provisioning before dispatching directives.

- The subagent coordinator places sequential specification roles into single-role waves to prevent divergence across spec boundaries.

- The subagent coordinator groups independent implementation roles into parallel execution waves when permitted by role dependency declarations.

- The subagent coordinator dispatches wave directives through the harness adapter and awaits turn results.

- The subagent coordinator drives the convergence loop across execution waves until all units in scope evaluate clean, a role fails, or maximum wave limits are reached.

- The subagent coordinator aggregates cumulative token consumption into monetary expenditures across all dispatched waves.
