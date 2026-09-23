from framework import operation, override, singleton_type
from typing import Mapping, Sequence
import antigravity_coordinator
import antigravity_mcp_client
import antigravity_sandbox_gate
import antigravity_telemetry

@singleton_type('system')
class AntigravityCoordinator(antigravity_coordinator.AntigravityCoordinator):
    """
PURPOSE:
Realizes deterministic orchestration, tiered worker retention, and wave action planning for Cleanroom convergence workflows.

GROUNDING_ARGUMENT:
- System singleton interacting with antigravity_mcp_client.AntigravityMcpClient, antigravity_sandbox_gate.AntigravitySandboxGate, and antigravity_telemetry.AntigravityTelemetry to orchestrate DAG convergence.
"""

    @operation
    @override
    def load_state(self, root: str, target: str) -> antigravity_coordinator.CoordinatorState:
        """
PURPOSE:
Reads coordinator state as JSON within the cleanroom state directory in the workspace root.

FRESH_REQUIREMENTS:
- Loading and saving state reads and writes coordinator state as JSON within the cleanroom state directory in the workspace root.

INHERITED_REQUIREMENTS:
- [AntigravityCoordinator] The antigravity coordinator reads coordinator state for a workspace root and target.

GROUNDING_ARGUMENT:
- Reads coordinator_state.json from the .cleanroom directory under root, returning deserialized CoordinatorState.
"""
        ...

    @operation
    @override
    def save_state(self, state: antigravity_coordinator.CoordinatorState, root: str) -> None:
        """
PURPOSE:
Writes coordinator state as JSON within the cleanroom state directory in the workspace root.

FRESH_REQUIREMENTS:
- Loading and saving state reads and writes coordinator state as JSON within the cleanroom state directory in the workspace root.

INHERITED_REQUIREMENTS:
- [AntigravityCoordinator] The antigravity coordinator writes coordinator state to a workspace root.

GROUNDING_ARGUMENT:
- Serializes CoordinatorState to JSON and writes atomically to .cleanroom/coordinator_state.json.
"""
        ...

    @operation
    @override
    def evaluate_pruning(self, state: antigravity_coordinator.CoordinatorState, config: antigravity_coordinator.CoordinatorConfig, now: float) -> Sequence[str]:
        """
PURPOSE:
Identifies workers with failed status or exceeding idle timeouts or token limits.

FRESH_REQUIREMENTS:
- Evaluating pruning identifies workers with failed status or exceeding idle timeouts or token limits.
- Workers with failed status are immediately marked for termination.
- Workers idle longer than the idle prune ttl sec timeout are marked for termination.
- Workers whose context tokens exceed the idle prune warm cap tokens ceiling and whose idle duration exceeds the idle prune warm ttl sec timeout are marked for termination.
- Pruned workers are removed from active coordinator state.

INHERITED_REQUIREMENTS:
- [AntigravityCoordinator] The antigravity coordinator determines worker identifiers to terminate based on worker failure status, idle timeouts, and context token caps.

GROUNDING_ARGUMENT:
- Iterates workers in state, checks for failed status or idle durations against config timeouts and token caps, pops pruned workers, and returns their conversation IDs.
"""
        ...

    @operation
    @override
    def is_worker_eligible_for_reuse(self, worker: antigravity_coordinator.WorkerState, units: Sequence[str], config: antigravity_coordinator.CoordinatorConfig, now: float) -> bool:
        """
PURPOSE:
Verifies idle status and tiered context limits based on worker age.

FRESH_REQUIREMENTS:
- Evaluating worker eligibility for reuse verifies idle status and tiered context limits based on worker age.
- When the worker age is less than the ttl fresh sec duration, the worker qualifies if its context tokens are below the cap fresh tokens ceiling.
- When the worker age is between the ttl fresh sec duration and the ttl max sec duration, the worker qualifies if its context tokens are below the cap warm tokens ceiling.
- Workers exceeding the ttl max sec duration or not in idle status do not qualify for reuse.

INHERITED_REQUIREMENTS:
- [AntigravityCoordinator] The antigravity coordinator checks whether a worker state qualifies for reuse given target units, coordinator config, and a current timestamp.

GROUNDING_ARGUMENT:
- Verifies worker status is idle, computes worker age, and compares context_tokens against age-tiered caps.
"""
        ...

    @operation
    @override
    def partition_batches(self, batch: Sequence[Mapping[str, str]], batch_size: int) -> Sequence[Sequence[Mapping[str, str]]]:
        """
PURPOSE:
Divides ready units into contiguous sub-batches bounded by the batch size limit to enable concurrent worker execution across independent units.

FRESH_REQUIREMENTS:
- Partitioning batches divides ready units into contiguous sub-batches bounded by the batch size limit to enable concurrent worker execution across independent units.

INHERITED_REQUIREMENTS:
- [AntigravityCoordinator] The antigravity coordinator divides a ready batch into clusters bounded by batch size.

GROUNDING_ARGUMENT:
- Slices the batch sequence into chunks of size batch_size.
"""
        ...

    @operation
    @override
    def plan_next_step(self, target: str, reports: Mapping[str, str], config: antigravity_coordinator.CoordinatorConfig, root: str, now: float, port: int) -> antigravity_coordinator.ActionPlan:
        """
PURPOSE:
Updates worker completion reports, refreshes token usage statistics from telemetry, prunes expired workers, ensures the server is active, and queries the next ready batch.

FRESH_REQUIREMENTS:
- Planning the next step updates worker completion reports, refreshes token usage statistics from telemetry, prunes expired workers, ensures the server is active, and queries the next ready batch.
- When worker reports indicate failures, failure counts for assigned units are incremented. If any unit exceeds the max retries per unit limit, DAG convergence is aborted and all workers are terminated. When worker reports indicate successful completion, failure counts for assigned units are cleared.
- Workers currently in busy status are in-flight; only idle workers are eligible for reuse or revives. If ready units are already assigned to in-flight busy workers, no redundant spawns or revives are generated. Newly spawned and revived workers are marked with busy status.
- When the subgraph is clean or no dirty nodes remain, all remaining workers are terminated, the server is shut down, and a completed action plan is returned.
- When a ready batch is returned, the batch is partitioned by batch size. For each partition, eligible warm workers matching the ready role are evaluated, preferring workers with unit footprint overlap and selecting the worker with the least conversation context tokens, falling back to eligible non-overlapping workers with least conversation context tokens. Assigned units are additively merged into the revived worker's unit footprint. If no eligible warm worker is found, a fresh worker is spawned.

INHERITED_REQUIREMENTS:
- [AntigravityCoordinator] The antigravity coordinator computes an action plan for a target, an active worker reports mapping, coordinator config, workspace root, timestamp, and a server port.

GROUNDING_ARGUMENT:
- Coordinates lifecycle updates, invokes AntigravityTelemetry to update context sizes, queries AntigravityMcpClient next_batch, partitions chunks, filters eligible candidate workers by least context tokens, binds sessions via AntigravitySandboxGate, additively merges footprints, and returns ActionPlan.
"""
        ...

    @operation
    @override
    def register_spawned_workers(self, spawned_map: Mapping[str, str], root: str, now: float) -> None:
        """
PURPOSE:
Associates newly spawned conversation identifiers with their assigned sessions, copying role and unit footprint from pending spawns into active worker state records with busy status.

FRESH_REQUIREMENTS:
- Registering spawned workers associates newly spawned conversation identifiers with their assigned sessions, copying role and unit footprint from pending spawns into active worker state records with busy status.

INHERITED_REQUIREMENTS:
- [AntigravityCoordinator] The antigravity coordinator associates newly spawned conversation identifiers with assigned sessions in coordinator state.

GROUNDING_ARGUMENT:
- For each spawned mapping, saves session in AntigravitySandboxGate, retrieves pending spawn info, and creates a WorkerState entry with busy status.
"""
        ...

    @operation
    @override
    def record_worker_status(self, session_id: str, status: str, root: str, now: float, unit: str='') -> None:
        """
PURPOSE:
Transitions a worker matching the session identifier to failed status upon failure or idle status upon completion, updates last active timestamp, and records unit failure counts or clears failure counts based on completion or failure status.

FRESH_REQUIREMENTS:
- Recording worker status transitions a worker matching the session identifier to failed status upon failure or idle status upon completion, updates last active timestamp, and records unit failure counts or clears failure counts based on completion or failure status.

INHERITED_REQUIREMENTS:
- [AntigravityCoordinator] The antigravity coordinator updates worker lifecycle status to idle or failed and updates unit failure counts for a session identifier in coordinator state.

GROUNDING_ARGUMENT:
- Loads coordinator state, locates worker matching session_id, updates status to failed or idle and last_active_at, adjusts failure_counts, and saves state.
"""
        ...

    @operation
    @override
    def ensure_server_running(self, port: int, batch_size: int, root: str) -> bool:
        """
PURPOSE:
Verifies FastMCP server availability, starting it in the background if absent.

FRESH_REQUIREMENTS:
- The antigravity coordinator verifies server availability on a port with the configured batch size.

INHERITED_REQUIREMENTS:
- [AntigravityCoordinator] The antigravity coordinator verifies server availability on a port with the configured batch size.

GROUNDING_ARGUMENT:
- Checks sentinel file liveness, launching cleanroom_mcp_runner_impl if not active.
"""
        ...
