from framework import operation, override, singleton_type
from typing import Mapping, Self, Sequence
import antigravity_coordinator
import antigravity_mcp_client
import antigravity_sandbox_gate
import antigravity_telemetry

@singleton_type('system')
class AntigravityCoordinator(antigravity_coordinator.AntigravityCoordinator):
    """Realizes deterministic orchestration, tiered worker retention, and wave action planning for Cleanroom convergence workflows.

    GROUNDING_ARGUMENT:
    - System singleton coordinating worker lifecycles, reading and writing state JSON, querying telemetry usage, managing sessions via sandbox gate, and resolving batches via MCP client.
    """

    @operation
    @override
    def load_state(self, root: str, target: str) -> antigravity_coordinator.CoordinatorState:
        """
        REQUIREMENTS:
        - Loading and saving state reads and writes coordinator state as JSON within the cleanroom state directory in the workspace root.

        GROUNDING_IMPLEMENTS:
        - action("read_coordinator_state", antigravity_coordinator.CoordinatorState): Reads coordinator state from JSON.
        """
        ...

    @operation
    @override
    def save_state(self, state: antigravity_coordinator.CoordinatorState, root: str) -> None:
        """
        REQUIREMENTS:
        - Loading and saving state reads and writes coordinator state as JSON within the cleanroom state directory in the workspace root.

        GROUNDING_IMPLEMENTS:
        - action("write_coordinator_state", None): Writes coordinator state to JSON.
        """
        ...

    @operation
    @override
    def evaluate_pruning(self, state: antigravity_coordinator.CoordinatorState, config: antigravity_coordinator.CoordinatorConfig, now: float) -> Sequence[str]:
        """
        REQUIREMENTS:
        - Evaluating pruning identifies workers with failed status or exceeding idle timeouts or token limits.
        - Workers with failed status are immediately marked for termination.
        - Workers idle longer than the idle prune ttl sec timeout are marked for termination.
        - Workers whose context tokens exceed the idle prune warm cap tokens ceiling and whose idle duration exceeds the idle prune warm ttl sec timeout are marked for termination.
        - Pruned workers are removed from active coordinator state.

        GROUNDING_PROVISIONS:
        - action("evaluate_worker_termination", Sequence[str]): Evaluates worker termination criteria.

        GROUNDING_ARGUMENT:
        - action("evaluate_worker_termination", Self) :- knows("idle_prune_ttl_sec", antigravity_coordinator.CoordinatorConfig), knows("idle_prune_warm_ttl_sec", antigravity_coordinator.CoordinatorConfig), knows("idle_prune_warm_cap_tokens", antigravity_coordinator.CoordinatorConfig), knows("worker_lifecycle_states", antigravity_coordinator.CoordinatorState).
        """
        ...

    @operation
    @override
    def is_worker_eligible_for_reuse(self, worker: antigravity_coordinator.WorkerState, units: Sequence[str], config: antigravity_coordinator.CoordinatorConfig, now: float) -> bool:
        """
        REQUIREMENTS:
        - Evaluating worker eligibility for reuse verifies idle status and tiered context limits based on worker age.
        - When the worker age is less than the ttl fresh sec duration, the worker qualifies if its context tokens are below the cap fresh tokens ceiling.
        - When the worker age is between the ttl fresh sec duration and the ttl max sec duration, the worker qualifies if its context tokens are below the cap warm tokens ceiling.
        - Workers exceeding the ttl max sec duration or not in idle status do not qualify for reuse.

        GROUNDING_PROVISIONS:
        - action("check_worker_reuse", bool): Evaluates worker qualification for reuse.

        GROUNDING_ARGUMENT:
        - action("check_worker_reuse", Self) :- knows("ttl_fresh_sec", antigravity_coordinator.CoordinatorConfig), knows("ttl_max_sec", antigravity_coordinator.CoordinatorConfig), knows("cap_fresh_tokens", antigravity_coordinator.CoordinatorConfig), knows("cap_warm_tokens", antigravity_coordinator.CoordinatorConfig), knows("worker_status", antigravity_coordinator.WorkerState).
        """
        ...

    @operation
    @override
    def partition_batches(self, batch: Sequence[Mapping[str, str]], batch_size: int) -> Sequence[Sequence[Mapping[str, str]]]:
        """
        REQUIREMENTS:
        - Partitioning batches divides ready units into contiguous sub-batches bounded by the batch size limit to enable concurrent worker execution across independent units.

        GROUNDING_PROVISIONS:
        - action("partition_ready_clusters", Sequence[Sequence[Mapping[str, str]]]): Divides ready units into sub-batches.

        GROUNDING_ARGUMENT:
        - action("partition_ready_clusters", Self) :- knows("batch_size", antigravity_coordinator.CoordinatorConfig).
        """
        ...

    @operation
    @override
    def plan_next_step(self, target: str, reports: Mapping[str, str], config: antigravity_coordinator.CoordinatorConfig, root: str, now: float, port: int) -> antigravity_coordinator.ActionPlan:
        """
        REQUIREMENTS:
        - Planning the next step updates worker completion reports, refreshes token usage statistics from telemetry, prunes expired workers, ensures the server is active, and queries the next ready batch.
        - When worker reports indicate failures, failure counts for assigned units are incremented. If any unit exceeds the max retries per unit limit, DAG convergence is aborted and all workers are terminated. When worker reports indicate successful completion, failure counts for assigned units are cleared.
        - Workers currently in busy status are in-flight; only idle workers are eligible for reuse or revives. If ready units are already assigned to in-flight busy workers, no redundant spawns or revives are generated. Newly spawned and revived workers are marked with busy status.
        - When the subgraph is clean or no dirty nodes remain, all remaining workers are terminated, the server is shut down, and a completed action plan is returned.
        - When a ready batch is returned, the batch is partitioned by batch size. For each partition, eligible warm workers matching the ready role are evaluated, preferring workers with unit footprint overlap and selecting the worker with the least conversation context tokens, falling back to eligible non-overlapping workers with least conversation context tokens. Assigned units are additively merged into the revived worker's unit footprint. Reviving a warm worker registers the new session on the Model Context Protocol server and records the session association in the sandbox gate. If no eligible warm worker is found, a fresh worker is spawned and its session is registered on the Model Context Protocol server.

        GROUNDING_PROVISIONS:
        - action("compute_orchestration_plan", antigravity_coordinator.ActionPlan): Plans next orchestration step.

        GROUNDING_ARGUMENT:
        - action("compute_orchestration_plan", Self) :- action("read_coordinator_state", Self), action("verify_server_availability", Self), action("extract_conversation_stats", antigravity_telemetry.AntigravityTelemetry), action("query_next_ready_wave", antigravity_mcp_client.AntigravityMcpClient), action("register_session", antigravity_mcp_client.AntigravityMcpClient), action("associate_worker_session", antigravity_sandbox_gate.AntigravitySandboxGate), action("stop_server", antigravity_mcp_client.AntigravityMcpClient), action("evaluate_worker_termination", Self), action("check_worker_reuse", Self), action("partition_ready_clusters", Self), action("write_coordinator_state", Self).
        """
        ...

    @operation
    @override
    def register_spawned_workers(self, spawned_map: Mapping[str, str], root: str, now: float) -> None:
        """
        REQUIREMENTS:
        - Registering spawned workers associates newly spawned conversation identifiers with their assigned sessions, copying role and unit footprint from pending spawns into active worker state records with busy status.

        GROUNDING_PROVISIONS:
        - action("assign_spawned_sessions", None): Registers spawned workers into state.

        GROUNDING_ARGUMENT:
        - action("assign_spawned_sessions", Self) :- action("read_coordinator_state", Self), action("associate_worker_session", antigravity_sandbox_gate.AntigravitySandboxGate), action("write_coordinator_state", Self).
        """
        ...

    @operation
    @override
    def record_worker_status(self, session_id: str, status: str, root: str, now: float, unit: str='') -> None:
        """
        REQUIREMENTS:
        - Recording worker status transitions a worker matching the session identifier to failed status upon failure or idle status upon completion, updates last active timestamp, and records unit failure counts or clears failure counts based on completion or failure status.

        GROUNDING_PROVISIONS:
        - action("update_worker_lifecycle", None): Records worker status and updates failure counts.

        GROUNDING_ARGUMENT:
        - action("update_worker_lifecycle", Self) :- action("read_coordinator_state", Self), action("write_coordinator_state", Self), knows("unit_failure_counts", antigravity_coordinator.CoordinatorState).
        """
        ...

    @operation
    @override
    def ensure_server_running(self, port: int, batch_size: int, root: str) -> bool:
        """
        REQUIREMENTS:
        - The antigravity coordinator ensures server availability on a configured port and batch size by checking active sentinel file presence and process liveness in the workspace root, removing stale sentinels, launching the cleanroom Model Context Protocol runner subprocess when inactive, and polling until the active sentinel file confirms process liveness.

        GROUNDING_IMPLEMENTS:
        - action("verify_server_availability", bool): Verifies server availability on port.
        """
        ...

