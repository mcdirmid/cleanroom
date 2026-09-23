# Requirements specified in antigravity_coordinator.pyi
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class CoordinatorConfig:
    ttl_fresh_sec: float = 300.0
    ttl_max_sec: float = 600.0
    cap_fresh_tokens: int = 200_000
    cap_warm_tokens: int = 100_000
    idle_prune_ttl_sec: float = 600.0
    idle_prune_warm_ttl_sec: float = 300.0
    idle_prune_warm_cap_tokens: int = 100_000
    batch_size: int = 10
    max_retries_per_unit: int = 1


@dataclass(frozen=True)
class WorkerState:
    conv_id: str
    role: str
    session_id: str
    created_at: float
    last_active_at: float
    unit_footprint: Sequence[str]
    context_tokens: int
    status: str


@dataclass(frozen=True)
class CoordinatorState:
    target: str
    session_counter: int
    workers: Mapping[str, WorkerState]
    pending_spawns: Mapping[str, Any]
    failure_counts: Mapping[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class ActionPlan:
    is_complete: bool
    kill: Sequence[str]
    spawns: Sequence[Mapping[str, Any]]
    revives: Sequence[Mapping[str, Any]]
    dirty_nodes: Sequence[str]
    summary: str


class AntigravityCoordinator:
    def load_state(self, root: str, target: str) -> CoordinatorState:
        raise NotImplementedError

    def save_state(self, state: CoordinatorState, root: str) -> None:
        raise NotImplementedError

    def evaluate_pruning(self, state: CoordinatorState, config: CoordinatorConfig, now: float) -> Sequence[str]:
        raise NotImplementedError

    def is_worker_eligible_for_reuse(self, worker: WorkerState, units: Sequence[str], config: CoordinatorConfig, now: float) -> bool:
        raise NotImplementedError

    def partition_batches(self, batch: Sequence[Mapping[str, str]], batch_size: int) -> Sequence[Sequence[Mapping[str, str]]]:
        raise NotImplementedError

    def plan_next_step(
        self,
        target: str,
        reports: Mapping[str, str],
        config: CoordinatorConfig,
        root: str,
        now: float,
        port: int,
    ) -> ActionPlan:
        raise NotImplementedError

    def register_spawned_workers(self, spawned_map: Mapping[str, str], root: str, now: float) -> None:
        raise NotImplementedError

    def record_worker_status(self, session_id: str, status: str, root: str, now: float, unit: str = "") -> None:
        raise NotImplementedError

    def ensure_server_running(self, port: int, batch_size: int, root: str) -> bool:
        raise NotImplementedError
