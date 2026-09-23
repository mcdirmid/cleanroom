from dataclasses import dataclass
from framework import data_type, operation, singleton_type
from typing import Any, Mapping, Sequence

@data_type
@dataclass(frozen=True)
class CoordinatorConfig:
    """
PURPOSE:
Encapsulates scheduling thresholds, exposing a ttl fresh sec duration, a ttl max sec duration, a cap fresh tokens ceiling, a cap warm tokens ceiling, an idle prune ttl sec timeout, an idle prune warm ttl sec timeout, an idle prune warm cap tokens ceiling, a batch size limit, and a max retries per unit limit.

FRESH_REQUIREMENTS:
- A coordinator config record encapsulates scheduling thresholds, exposing a ttl fresh sec duration, a ttl max sec duration, a cap fresh tokens ceiling, a cap warm tokens ceiling, an idle prune ttl sec timeout, an idle prune warm ttl sec timeout, an idle prune warm cap tokens ceiling, a batch size limit, and a max retries per unit limit.
"""

    def __init__(self, ttl_fresh_sec: float=300.0, ttl_max_sec: float=600.0, cap_fresh_tokens: int=200000, cap_warm_tokens: int=100000, idle_prune_ttl_sec: float=600.0, idle_prune_warm_ttl_sec: float=300.0, idle_prune_warm_cap_tokens: int=100000, batch_size: int=10, max_retries_per_unit: int=1) -> None:
        ...

    @property
    def ttl_fresh_sec(self) -> float:
        """
PURPOSE:
Exposes maximum age duration for fresh worker reuse under fresh token cap.
"""
        ...

    @property
    def ttl_max_sec(self) -> float:
        """
PURPOSE:
Exposes maximum age duration for warm worker reuse under warm token cap.
"""
        ...

    @property
    def cap_fresh_tokens(self) -> int:
        """
PURPOSE:
Exposes context token cap for workers under fresh age threshold.
"""
        ...

    @property
    def cap_warm_tokens(self) -> int:
        """
PURPOSE:
Exposes context token cap for workers between fresh and maximum age thresholds.
"""
        ...

    @property
    def idle_prune_ttl_sec(self) -> float:
        """
PURPOSE:
Exposes idle duration threshold after which any worker is pruned.
"""
        ...

    @property
    def idle_prune_warm_ttl_sec(self) -> float:
        """
PURPOSE:
Exposes idle duration threshold after which workers exceeding warm cap are pruned.
"""
        ...

    @property
    def idle_prune_warm_cap_tokens(self) -> int:
        """
PURPOSE:
Exposes context token threshold triggering accelerated idle pruning.
"""
        ...

    @property
    def batch_size(self) -> int:
        """
PURPOSE:
Exposes unit limit triggering parallel batch partitioning.
"""
        ...

    @property
    def max_retries_per_unit(self) -> int:
        """
PURPOSE:
Exposes maximum failure retry attempts allowed per unit before aborting convergence.
"""
        ...

@data_type
@dataclass(frozen=True)
class WorkerState:
    """
PURPOSE:
Maintains lifecycle data for a subagent worker, exposing a conv id, a role, a session id, a created at timestamp, a last active at timestamp, a unit footprint sequence, a context tokens size, and a status.

FRESH_REQUIREMENTS:
- A worker state record maintains lifecycle data for a subagent worker, exposing a conv id, a role, a session id, a created at timestamp, a last active at timestamp, a unit footprint sequence, a context tokens size, and a status.
"""

    def __init__(self, conv_id: str, role: str, session_id: str, created_at: float, last_active_at: float, unit_footprint: Sequence[str], context_tokens: int, status: str) -> None:
        ...

    @property
    def conv_id(self) -> str:
        """
PURPOSE:
Exposes conversation identifier of the subagent worker.
"""
        ...

    @property
    def role(self) -> str:
        """
PURPOSE:
Exposes assigned role address of the worker.
"""
        ...

    @property
    def session_id(self) -> str:
        """
PURPOSE:
Exposes current Model Context Protocol session identifier.
"""
        ...

    @property
    def created_at(self) -> float:
        """
PURPOSE:
Exposes worker spawn timestamp.
"""
        ...

    @property
    def last_active_at(self) -> float:
        """
PURPOSE:
Exposes timestamp of latest worker completion or activity.
"""
        ...

    @property
    def unit_footprint(self) -> Sequence[str]:
        """
PURPOSE:
Exposes sequence of unit addresses touched by this worker.
"""
        ...

    @property
    def context_tokens(self) -> int:
        """
PURPOSE:
Exposes latest measured context token size.
"""
        ...

    @property
    def status(self) -> str:
        """
PURPOSE:
Exposes worker state string (idle or busy).
"""
        ...

@data_type
@dataclass(frozen=True)
class CoordinatorState:
    """
PURPOSE:
Persists state across execution turns, exposing a target unit, a session counter, a workers mapping, a pending spawns mapping, and a failure counts mapping.

FRESH_REQUIREMENTS:
- A coordinator state record persists state across execution turns, exposing a target unit, a session counter, a workers mapping, a pending spawns mapping, and a failure counts mapping.
"""

    def __init__(self, target: str, session_counter: int, workers: Mapping[str, WorkerState], pending_spawns: Mapping[str, Any], failure_counts: Mapping[str, int]={}) -> None:
        ...

    @property
    def target(self) -> str:
        """
PURPOSE:
Exposes target root address being converged.
"""
        ...

    @property
    def session_counter(self) -> int:
        """
PURPOSE:
Exposes monotonically increasing session sequence counter.
"""
        ...

    @property
    def workers(self) -> Mapping[str, WorkerState]:
        """
PURPOSE:
Exposes dictionary mapping conversation identifiers to worker states.
"""
        ...

    @property
    def pending_spawns(self) -> Mapping[str, Any]:
        """
PURPOSE:
Exposes dictionary mapping session identifiers to pending spawn metadata.
"""
        ...

    @property
    def failure_counts(self) -> Mapping[str, int]:
        """
PURPOSE:
Exposes dictionary mapping unit addresses to consecutive failure counts.
"""
        ...

@data_type
@dataclass(frozen=True)
class ActionPlan:
    """
PURPOSE:
Defines actions for an orchestration turn, exposing an is complete indicator, a kill list, a spawns list, a revives list, a dirty nodes list, and a summary description.

FRESH_REQUIREMENTS:
- An action plan record defines actions for an orchestration turn, exposing an is complete indicator, a kill list, a spawns list, a revives list, a dirty nodes list, and a summary description.
"""

    def __init__(self, is_complete: bool, kill: Sequence[str], spawns: Sequence[Mapping[str, Any]], revives: Sequence[Mapping[str, Any]], dirty_nodes: Sequence[str], summary: str) -> None:
        ...

    @property
    def is_complete(self) -> bool:
        """
PURPOSE:
Indicates whether full convergence has been achieved.
"""
        ...

    @property
    def kill(self) -> Sequence[str]:
        """
PURPOSE:
List of conversation identifiers to terminate.
"""
        ...

    @property
    def spawns(self) -> Sequence[Mapping[str, Any]]:
        """
PURPOSE:
List of worker subagents to spawn.
"""
        ...

    @property
    def revives(self) -> Sequence[Mapping[str, Any]]:
        """
PURPOSE:
List of messages to send to warm workers.
"""
        ...

    @property
    def dirty_nodes(self) -> Sequence[str]:
        """
PURPOSE:
List of dirty node addresses remaining.
"""
        ...

    @property
    def summary(self) -> str:
        """
PURPOSE:
Diagnostic summary of the action plan.
"""
        ...

@singleton_type('system')
class AntigravityCoordinator:
    """
PURPOSE:
System service that computes deterministic orchestration decisions.
"""

    @operation
    def load_state(self, root: str, target: str) -> CoordinatorState:
        """
PURPOSE:
Reads coordinator state for a workspace root and target.

FRESH_REQUIREMENTS:
- The antigravity coordinator reads coordinator state for a workspace root and target.
"""
        ...

    @operation
    def save_state(self, state: CoordinatorState, root: str) -> None:
        """
PURPOSE:
Writes coordinator state to a workspace root.

FRESH_REQUIREMENTS:
- The antigravity coordinator writes coordinator state to a workspace root.
"""
        ...

    @operation
    def evaluate_pruning(self, state: CoordinatorState, config: CoordinatorConfig, now: float) -> Sequence[str]:
        """
PURPOSE:
Determines worker identifiers to terminate based on worker failure status, idle timeouts, and context token caps.

FRESH_REQUIREMENTS:
- The antigravity coordinator determines worker identifiers to terminate based on worker failure status, idle timeouts, and context token caps.
"""
        ...

    @operation
    def is_worker_eligible_for_reuse(self, worker: WorkerState, units: Sequence[str], config: CoordinatorConfig, now: float) -> bool:
        """
PURPOSE:
Checks whether a worker state qualifies for reuse given target units, coordinator config, and a current timestamp.

FRESH_REQUIREMENTS:
- The antigravity coordinator checks whether a worker state qualifies for reuse given target units, coordinator config, and a current timestamp.
"""
        ...

    @operation
    def partition_batches(self, batch: Sequence[Mapping[str, str]], batch_size: int) -> Sequence[Sequence[Mapping[str, str]]]:
        """
PURPOSE:
Divides a ready batch into clusters bounded by batch size.

FRESH_REQUIREMENTS:
- The antigravity coordinator divides a ready batch into clusters bounded by batch size.
"""
        ...

    @operation
    def plan_next_step(self, target: str, reports: Mapping[str, str], config: CoordinatorConfig, root: str, now: float, port: int) -> ActionPlan:
        """
PURPOSE:
Computes an action plan for a target, an active worker reports mapping, coordinator config, workspace root, timestamp, and a server port.

FRESH_REQUIREMENTS:
- The antigravity coordinator computes an action plan for a target, an active worker reports mapping, coordinator config, workspace root, timestamp, and a server port.
"""
        ...

    @operation
    def register_spawned_workers(self, spawned_map: Mapping[str, str], root: str, now: float) -> None:
        """
PURPOSE:
Associates newly spawned conversation identifiers with assigned sessions in coordinator state.

FRESH_REQUIREMENTS:
- The antigravity coordinator associates newly spawned conversation identifiers with assigned sessions in coordinator state.
"""
        ...

    @operation
    def record_worker_status(self, session_id: str, status: str, root: str, now: float, unit: str='') -> None:
        """
PURPOSE:
Updates worker lifecycle status to idle or failed and updates unit failure counts for a session identifier in coordinator state.

FRESH_REQUIREMENTS:
- The antigravity coordinator updates worker lifecycle status to idle or failed and updates unit failure counts for a session identifier in coordinator state.
"""
        ...

    @operation
    def ensure_server_running(self, port: int, batch_size: int, root: str) -> bool:
        """
PURPOSE:
Verifies server availability on a port with the configured batch size.

FRESH_REQUIREMENTS:
- The antigravity coordinator verifies server availability on a port with the configured batch size.
"""
        ...
