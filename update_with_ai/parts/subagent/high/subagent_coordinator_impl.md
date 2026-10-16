<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-12T21:00:00Z
CHANGE: author subagent_coordinator_impl implementation specification
CODE_HASH: b93703556435
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->

# subagent_coordinator_impl implementation component

imports: agent_session, subagent_coordinator, workspace_provision, workspace_registry, workspace_work
implements: subagent_coordinator

## Purpose

The subagent_coordinator_impl implementation component realizes zero-execution multi-agent workspace coordination, dynamic queue-driven process supervision, fine-grained concurrency, and iterative loop convergence across external harness adapters.

Complex software development methodologies partition work into specialized roles that depend on upstream artifacts. Executing these roles with rigid static waves or hardcoded role assumptions leads to artificial serialization, idle worker capacity, and invalidated context. The subagent_coordinator_impl implementation component formalizes dynamic queue-driven process supervision, fine-grained node concurrency, harness abstraction, turn result aggregation, blame defect propagation, model configuration resolution, and cumulative token rate-card accounting.

**Out of scope:** The subagent_coordinator_impl implementation component does not directly execute subagent processes or mutate workspace files; these are handled by other components.

**Delegated:** Session lifecycle scoping is delegated to agent_session; workspace role discovery and root resolution are delegated to workspace_registry; queue evaluation and pending target tracking are delegated to workspace_work; role workspace provisioning is delegated to workspace_provision.

## Types and Behavior

The subagent coordinator realization schedules and coordinates autonomous subagents across role workspaces within an agent session.

When coordinating multi-agent execution:

- The realization resets preexisting role workspaces for declared roles upon initiating orchestration.

- The realization resolves subagent batch sizes and conversation token limits from declarative model configurations matching designated model names or identifiers.

- The realization queries commissioned workspaces and evaluates unblocked dirty role work queues.

- The realization bounds role discovery and execution up to an optional target role boundary when specified.

- The realization commissions absent role workspaces on demand when ready tasks are identified, recording effective batch size limits into role descriptors.

- The realization dispatches role directives concurrently for roles possessing ready work, tracking active worker handles without static wave partitioning.

- The realization periodically polls active workers through non-blocking checks on the configured harness adapter at a configurable interval (defaulting to 10 seconds), collecting role turn results upon completion.

- The realization tracks consecutive unproductive turns where a role yields zero submitted and zero blamed targets, halting orchestration when unproductive turns exceed a threshold (defaulting to 2).

- The realization emits real-time progress notifications detailing role dispatch, turn outcomes, token consumption, and work queue state.

- The realization manages the dynamic supervision loop, continuing until all units evaluate clean, a turn reports failure, or maximum wave iterations are reached.

- The realization automatically deletes all provisioned role workspaces in scope upon achieving clean convergence.

- The realization normalizes token metrics from turn outcomes and tallies total costs according to model pricing rate cards.
