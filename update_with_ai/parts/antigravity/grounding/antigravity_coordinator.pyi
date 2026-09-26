from dataclasses import dataclass
from framework import data_type, operation, singleton_type
from typing import Any, Mapping, Sequence

@data_type
@dataclass(frozen=True)
class CoordinatorConfig:
    """Encapsulates scheduling thresholds.

    REQUIREMENTS:
    - A coordinator config record encapsulates scheduling thresholds, exposing a ttl fresh sec duration, a ttl max sec duration, a cap fresh tokens ceiling, a cap warm tokens ceiling, an idle prune ttl sec timeout, an idle prune warm ttl sec timeout, an idle prune warm cap tokens ceiling, a batch size limit, and a max retries per unit limit.

    GROUNDING_PROVISIONS:
    - knows("ttl_fresh_sec", Self)
    - knows("ttl_max_sec", Self)
    - knows("cap_fresh_tokens", Self)
    - knows("cap_warm_tokens", Self)
    - knows("idle_prune_ttl_sec", Self)
    - knows("idle_prune_warm_ttl_sec", Self)
    - knows("idle_prune_warm_cap_tokens", Self)
    - knows("batch_size", Self)
    - knows("max_retries_per_unit", Self)
    """

    def __init__(self, ttl_fresh_sec: float=300.0, ttl_max_sec: float=600.0, cap_fresh_tokens: int=200000, cap_warm_tokens: int=100000, idle_prune_ttl_sec: float=600.0, idle_prune_warm_ttl_sec: float=300.0, idle_prune_warm_cap_tokens: int=100000, batch_size: int=10, max_retries_per_unit: int=1) -> None:
        ...

    @property
    def ttl_fresh_sec(self) -> float:
        ...

    @property
    def ttl_max_sec(self) -> float:
        ...

    @property
    def cap_fresh_tokens(self) -> int:
        ...

    @property
    def cap_warm_tokens(self) -> int:
        ...

    @property
    def idle_prune_ttl_sec(self) -> float:
        ...

    @property
    def idle_prune_warm_ttl_sec(self) -> float:
        ...

    @property
    def idle_prune_warm_cap_tokens(self) -> int:
        ...

    @property
    def batch_size(self) -> int:
        ...

    @property
    def max_retries_per_unit(self) -> int:
        ...

@data_type
@dataclass(frozen=True)
class WorkerState:
    """Maintains lifecycle data for a subagent worker.

    REQUIREMENTS:
    - A worker state record maintains lifecycle data for a subagent worker, exposing a conv id, a role, a session id, a created at timestamp, a last active at timestamp, a unit footprint sequence, a context tokens size, and a status.

    GROUNDING_PROVISIONS:
    - knows("conv_id", Self)
    - knows("role", Self)
    - knows("session_id", Self)
    - knows("created_at", Self)
    - knows("last_active_at", Self)
    - knows("unit_footprint", Self)
    - knows("context_tokens", Self)
    - knows("status", Self)
    """

    def __init__(self, conv_id: str, role: str, session_id: str, created_at: float, last_active_at: float, unit_footprint: Sequence[str], context_tokens: int, status: str) -> None:
        ...

    @property
    def conv_id(self) -> str:
        ...

    @property
    def role(self) -> str:
        ...

    @property
    def session_id(self) -> str:
        ...

    @property
    def created_at(self) -> float:
        ...

    @property
    def last_active_at(self) -> float:
        ...

    @property
    def unit_footprint(self) -> Sequence[str]:
        ...

    @property
    def context_tokens(self) -> int:
        ...

    @property
    def status(self) -> str:
        ...

@data_type
@dataclass(frozen=True)
class CoordinatorState:
    """Persists state across execution turns.

    REQUIREMENTS:
    - A coordinator state record persists state across execution turns, exposing a target unit, a session counter, a workers mapping, a pending spawns mapping, and a failure counts mapping.

    GROUNDING_PROVISIONS:
    - knows("target", Self)
    - knows("session_counter", Self)
    - knows("workers", Self)
    - knows("pending_spawns", Self)
    - knows("failure_counts", Self)
    """

    def __init__(self, target: str, session_counter: int, workers: Mapping[str, WorkerState], pending_spawns: Mapping[str, Any], failure_counts: Mapping[str, int]={}) -> None:
        ...

    @property
    def target(self) -> str:
        ...

    @property
    def session_counter(self) -> int:
        ...

    @property
    def workers(self) -> Mapping[str, WorkerState]:
        ...

    @property
    def pending_spawns(self) -> Mapping[str, Any]:
        ...

    @property
    def failure_counts(self) -> Mapping[str, int]:
        ...

@data_type
@dataclass(frozen=True)
class ActionPlan:
    """Defines actions for an orchestration turn.

    REQUIREMENTS:
    - An action plan record defines actions for an orchestration turn, exposing an is complete indicator, a kill list, a spawns list, a revives list, a dirty nodes list, and a summary description.

    GROUNDING_PROVISIONS:
    - knows("is_complete", Self)
    - knows("kill", Self)
    - knows("spawns", Self)
    - knows("revives", Self)
    - knows("dirty_nodes", Self)
    - knows("summary", Self)
    """

    def __init__(self, is_complete: bool, kill: Sequence[str], spawns: Sequence[Mapping[str, Any]], revives: Sequence[Mapping[str, Any]], dirty_nodes: Sequence[str], summary: str) -> None:
        ...

    @property
    def is_complete(self) -> bool:
        ...

    @property
    def kill(self) -> Sequence[str]:
        ...

    @property
    def spawns(self) -> Sequence[Mapping[str, Any]]:
        ...

    @property
    def revives(self) -> Sequence[Mapping[str, Any]]:
        ...

    @property
    def dirty_nodes(self) -> Sequence[str]:
        ...

    @property
    def summary(self) -> str:
        ...

@singleton_type('system')
class AntigravityCoordinator:
    """System service that computes deterministic orchestration decisions.

    REQUIREMENTS:
    - The antigravity coordinator reads coordinator state for a workspace root and target.
    - The antigravity coordinator writes coordinator state to a workspace root.
    - The antigravity coordinator determines worker identifiers to terminate based on worker failure status, idle timeouts, and context token caps.
    - The antigravity coordinator checks whether a worker state qualifies for reuse given target units, coordinator config, and a current timestamp.
    - The antigravity coordinator divides a ready batch into clusters bounded by batch size.
    - The antigravity coordinator computes an action plan for a target, an active worker reports mapping, coordinator config, workspace root, timestamp, and a server port.
    - The antigravity coordinator associates newly spawned conversation identifiers with assigned sessions in coordinator state.
    - The antigravity coordinator updates worker lifecycle status to idle or failed and updates unit failure counts for a session identifier in coordinator state.
    - The antigravity coordinator verifies server availability on a port with the configured batch size.

    GROUNDING_PROVISIONS:
    - action("read_coordinator_state", CoordinatorState): Reads persisted coordinator state.
    - action("write_coordinator_state", None): Writes coordinator state to workspace storage.
    - action("evaluate_worker_termination", Sequence[str]): Evaluates worker termination criteria.
    - action("check_worker_reuse", bool): Evaluates worker qualification for reuse.
    - action("partition_ready_clusters", Sequence[Sequence[Mapping[str, str]]]): Partitions ready nodes into bounded clusters.
    - action("compute_orchestration_plan", ActionPlan): Computes action plan for orchestration turn.
    - action("assign_spawned_sessions", None): Associates newly spawned conversations with sessions.
    - action("update_worker_lifecycle", None): Updates worker status and failure counts.
    - action("verify_server_availability", bool): Verifies server port availability.
    """

    @operation
    def load_state(self, root: str, target: str) -> CoordinatorState:
        ...

    @operation
    def save_state(self, state: CoordinatorState, root: str) -> None:
        ...

    @operation
    def evaluate_pruning(self, state: CoordinatorState, config: CoordinatorConfig, now: float) -> Sequence[str]:
        ...

    @operation
    def is_worker_eligible_for_reuse(self, worker: WorkerState, units: Sequence[str], config: CoordinatorConfig, now: float) -> bool:
        ...

    @operation
    def partition_batches(self, batch: Sequence[Mapping[str, str]], batch_size: int) -> Sequence[Sequence[Mapping[str, str]]]:
        ...

    @operation
    def plan_next_step(self, target: str, reports: Mapping[str, str], config: CoordinatorConfig, root: str, now: float, port: int) -> ActionPlan:
        ...

    @operation
    def register_spawned_workers(self, spawned_map: Mapping[str, str], root: str, now: float) -> None:
        ...

    @operation
    def record_worker_status(self, session_id: str, status: str, root: str, now: float, unit: str='') -> None:
        ...

    @operation
    def ensure_server_running(self, port: int, batch_size: int, root: str) -> bool:
        ...
