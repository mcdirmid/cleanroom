<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T01:05:05Z
LAST_CHANGED: 2026-10-12T21:00:00Z
CHANGE: author subagent_coordinator_impl implementation specification
CODE_HASH: 4b08bbaf9b19
SPEC_QA_AUDIT: 2026-10-13T01:05:05Z
-->

# subagent_coordinator_impl implementation component

imports: agent_session, subagent_coordinator, workspace_provision, workspace_registry, workspace_work
implements: subagent_coordinator

## Purpose

The subagent_coordinator_impl implementation component realizes zero-execution multi-agent workspace coordination, DAG wave partitioning, concurrent wave execution, and iterative loop convergence across external harness adapters.

Complex software development methodologies partition work into specialized roles that depend on upstream artifacts. Executing these roles concurrently without ordering guarantees leads to cache thrashing, race conditions, and invalidated context. The subagent_coordinator_impl implementation component formalizes topological wave clustering, parallel and sequential execution waves, harness abstraction, turn result aggregation, blame defect propagation, and cumulative token rate-card accounting.

**Out of scope:** The subagent_coordinator_impl implementation component does not directly execute subagent processes or mutate workspace files; these are handled by other components.

**Delegated:** Session lifecycle scoping is delegated to agent_session; workspace role discovery and root resolution are delegated to workspace_registry; queue evaluation and pending target tracking are delegated to workspace_work; role workspace provisioning is delegated to workspace_provision.

## Types and Behavior

The subagent coordinator realization schedules and coordinates autonomous subagents across role workspaces within an agent session.

When coordinating multi-agent execution:

- The realization queries commissioned workspaces and evaluates dirty role work queues.

- The realization commissions absent role workspaces when ready tasks are identified.

- The realization groups dirty roles into sequential specification waves and parallel implementation waves according to declared role dependencies.

- The realization dispatches role directives through the configured harness adapter, collecting role turn results.

- The realization manages the convergence loop across execution waves, continuing until all units evaluate clean, a turn reports failure, or maximum wave iterations are reached.

- The realization normalizes token metrics from turn outcomes and tallies total costs according to model pricing rate cards.
