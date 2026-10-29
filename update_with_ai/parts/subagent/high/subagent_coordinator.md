# subagent_coordinator interface component

imports: session

## Purpose

The subagent_coordinator interface component defines data types and operational contracts for zero-execution multi-agent workspace coordination across dynamic queue-driven process supervision and pluggable execution harnesses.

Complex software development methodologies partition work into specialized roles that depend on upstream artifacts. Executing these roles with rigid static waves or hardcoded role assumptions leads to artificial serialization, idle worker capacity, and invalidated context. The subagent_coordinator interface component formalizes dynamic queue-driven process supervision, fine-grained node concurrency, harness abstraction, round result aggregation, blame defect propagation, model configuration resolution, and cumulative token rate-card accounting.

**Out of scope:** The subagent_coordinator interface component does not directly execute subagent processes or mutate workspace files; these are handled by other components.

**Delegated:** Session lifecycle scoping is delegated to agent_session.

## Types and Behavior

A *token usage record* tracks uncached prompt tokens, cached prompt tokens, completion tokens, total tokens, and financial expenditure in USD.

A *role dispatch directive* captures the parameters required to execute an agent round within an isolated role workspace, including the target role name, workspace directory, directory scope, ready target paths, optional batch size bounding, and formatted instruction prompt.

A *role round result* captures the outcome of an autonomous subagent round, including the role identifier, outcome status (clean, blamed, unresolved, or failed), sequences of submitted targets and blamed targets, optional failure diagnostics, token telemetry, and elapsed execution time.

An *orchestration summary* captures the cumulative outcome of multi-role supervision, including convergence status, total waves executed, total units submitted, total units blamed, cumulative token usage telemetry, and diagnostic status messages.

An abstract *harness adapter* defines the execution protocol for dispatching role directives, non-blocking polling of round outcomes, awaiting round results, and interrupting runaway rounds.

A system's *subagent coordinator* schedules and orchestrates autonomous subagents across role workspaces within an agent session.

When coordinating multi-agent execution:

- The subagent coordinator provides dynamic model parameter resolution (`resolve_model_parameters`) to extract batch sizes, conversation token limits, and maximum unproductive round thresholds from declarative model configurations.

- The subagent coordinator resets preexisting role workspaces upon initiating orchestration to ensure clean initial state.

- The subagent coordinator dynamically resolves subagent batch sizes, conversation token limits, and maximum unproductive round thresholds from declarative model configurations matching designated model names or identifiers.

- The subagent coordinator evaluates DAG work queues across declared roles, dynamically identifying roles with ready work up to an optional target role boundary without static role hardcoding.

- The subagent coordinator restricts work queue evaluation to a designated target unit and its transitive upstream dependencies when a target unit is specified.

- The subagent coordinator ensures absent role workspaces are commissioned via workspace provisioning on demand before dispatching directives, persisting effective batch size bounds into workspace configurations.

- The subagent coordinator dispatches role directives to unblocked ready roles concurrently, tracking active worker handles without static wave partitioning, evaluating unblocked work queues across inactive roles on each polling interval to dispatch newly ready roles without awaiting completion of active workers.

- The subagent coordinator periodically polls active workers through the harness adapter at a configurable polling interval (defaulting to 10 seconds), reaping completed rounds, interrupting idling workers holding zero pending work items across consecutive polling intervals, and propagating blame defects into the build graph.

- The subagent coordinator tracks consecutive unproductive rounds yielding zero submitted and zero blamed targets, halting orchestration when unproductive rounds on unresolved targets exceed a threshold configured per model or globally (defaulting to 5).

- When an active worker completes a round without submitting, blaming, or failing its assigned targets, the subagent coordinator tracks the unresolved status and injects an actionable reminder into the subsequent role dispatch directive, reminding the worker that conversational commentary without tools is prohibited and that it must verify targets via check_files and conclude the round via submit, blame, or fail.

- The subagent coordinator emits real-time progress notifications detailing role dispatch, round outcomes, token consumption, and work queue state.

- The subagent coordinator drives the supervision loop until all units in scope evaluate clean, a role reports failure, or maximum wave limits are reached.

- The subagent coordinator automatically deletes all provisioned role workspaces in scope upon achieving clean convergence.

- The subagent coordinator interrupts all active workers and automatically deletes all provisioned role workspaces in scope when orchestration is interrupted by system termination or user cancellation signals.

- The subagent coordinator aggregates cumulative token consumption into monetary expenditures across all dispatched roles.

- Canonical log directory discovery resolves the canonical logs directory for a role workspace by querying the workspace registry for the repository root or traversing parent directories to locate the root logs directory.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-28T20:20:00Z
CHANGE: Asynchronous unblocked role dispatch and idle worker reaping
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->
