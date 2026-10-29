# subagent_coordinator_impl implementation component

imports: session, subagent_coordinator, provision, role_registry, work
implements: subagent_coordinator

## Purpose

The subagent_coordinator_impl implementation component realizes zero-execution multi-agent workspace coordination, dynamic queue-driven process supervision, fine-grained concurrency, and iterative loop convergence across external harness adapters.

Complex software development methodologies partition work into specialized roles that depend on upstream artifacts. Executing these roles with rigid static waves or hardcoded role assumptions leads to artificial serialization, idle worker capacity, and invalidated context. The subagent_coordinator_impl implementation component formalizes dynamic queue-driven process supervision, fine-grained node concurrency, harness abstraction, round result aggregation, blame defect propagation, model configuration resolution, and cumulative token rate-card accounting.

**Out of scope:** The subagent_coordinator_impl implementation component does not directly execute subagent processes or mutate workspace files; these are handled by other components.

**Delegated:** Session lifecycle scoping is delegated to agent_session; workspace role discovery and root resolution are delegated to role_registry; queue evaluation and pending target tracking are delegated to work; role workspace provisioning is delegated to provision.

## Types and Behavior

The subagent coordinator realization schedules and coordinates autonomous subagents across role workspaces within an agent session.

When coordinating multi-agent execution:

- The realization resets preexisting role workspaces for declared roles upon initiating orchestration.

- The realization resolves subagent batch sizes, conversation token limits, and maximum unproductive round thresholds from declarative model configurations matching designated model names or identifiers.

- The realization queries commissioned workspaces and evaluates unblocked dirty role work queues.

- The realization bounds role discovery and execution up to an optional target role boundary when specified, and restricts work discovery to a designated target unit and its transitive upstream dependencies when a target unit is specified. When the designated target role is a fused role definition, role workspace provisioning and execution are restricted exclusively to that fused role.

- The realization commissions absent role workspaces on demand when ready tasks are identified, recording effective batch size limits into role descriptors.

- The realization dispatches role directives concurrently for roles possessing ready work, tracking active worker handles without static wave partitioning, evaluating unblocked dirty work queues across inactive roles on each polling interval to dispatch newly ready roles immediately without waiting for in-flight active workers to conclude.

- The realization periodically polls active workers through non-blocking checks on the configured harness adapter at a configurable interval (defaulting to 10 seconds), collecting role round results upon completion, and interrupting idling workers that have resolved all assigned targets and hold zero pending work items across consecutive polling intervals.

- The realization tracks consecutive unproductive rounds where a role yields zero submitted and zero blamed targets and its assigned ready targets remain unresolved in the repository, suppressing unproductive round tracking and scolding reminders when assigned ready targets were resolved or cleaned in the repository during the round, and halting orchestration when consecutive unproductive rounds exceed a threshold configured per model or globally (defaulting to 5).

- When an active worker finishes a round without submitting, blaming, or failing assigned targets and its assigned ready targets remain unresolved in the repository, the realization preserves an unresolved reminder directive and injects it into the task prompt of the subsequent role dispatch directive, reminding the worker that conversational commentary without tools is prohibited while work remains, requiring ready targets to be resolved via check_files and submit, blame, or fail, and directing the worker to conclude immediately with summary text and no tool calls once no work remains.

- When supervising a fused role worker, upon receiving a completion notification the realization executes formal verification across the targets in the fused workspace, delivering error diagnostics to the worker with up to a hardcoded maximum of 3 retries on verification failure, and upon successful verification atomically harvesting modified files, stamping audit tags and change summaries, and marking all constituent targets clean in the repository.

- The realization emits real-time progress notifications detailing role dispatch, round outcomes, token consumption, and work queue state.

- The realization manages the dynamic supervision loop, continuing until all units evaluate clean, a round reports failure, or maximum wave iterations are reached, draining or cleanly interrupting in-flight active workers upon termination.

- The realization automatically deletes all provisioned role workspaces in scope upon achieving clean convergence.

- The realization interrupts all active workers and automatically deletes all provisioned role workspaces in scope when orchestration is interrupted by system termination or user cancellation signals.

- The realization normalizes token metrics from round outcomes and tallies total costs according to model pricing rate cards.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-26T20:38:00Z
LAST_CHANGED: 2026-10-28T20:20:00Z
CHANGE: Asynchronous unblocked role dispatch and idle worker reaping
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->
