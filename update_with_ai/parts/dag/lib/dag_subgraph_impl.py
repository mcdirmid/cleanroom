# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
# LAST_CHANGED: 2026-10-09T04:49:11Z
# CHANGE: Eliminate unreachable unready dependency break branch in next_ready_batch
# CODE_HASH: 8c02c7d79873
# COVERAGE_AUDIT: 2026-10-09T21:19:01Z
# QA_AUDIT: 2026-10-09T21:19:01Z
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from typing import Dict, List, Optional, Sequence, Set, Tuple
from support.lib.lifecycle import (
    InTier,
    LifecycleRegistry,
    Singleton,
    SystemTier,
    get_default_registry,
    get_singleton,
    system,
)
from .dag_storage import DagNode, DagStorage
from . import dag_config
from . import dag_subgraph

# Requirements specified in dag_subgraph_impl.pyi

class DagSubgraph(dag_subgraph.DagSubgraph, InTier[SystemTier], Singleton):
    tier = system

    def __init__(self) -> None:
        self._target: Optional[DagNode] = None
        self._topological_order: List[DagNode] = []
        self._visit_counts: Dict[DagNode, int] = {}

    def set_target(self, target: DagNode) -> None:
        self._target = target
        storage = get_singleton(DagStorage)

        reachable: Set[DagNode] = set()
        queue: List[DagNode] = [target]
        reachable.add(target)
        while queue:
            curr = queue.pop(0)
            for dep in storage.get_dependencies(curr):
                if dep.node not in reachable:
                    reachable.add(dep.node)
                    queue.append(dep.node)

        def _clean_role(r: str) -> str:
            return r.split(":")[-1].strip().lower()

        role_deps: Dict[str, Set[str]] = {}
        for n in reachable:
            r_n = _clean_role(str(n.role_address))
            if r_n not in role_deps:
                role_deps[r_n] = set()
            for dep in storage.get_dependencies(n):
                r_dep = _clean_role(str(dep.node.role_address))
                if r_dep != r_n:
                    role_deps[r_n].add(r_dep)

        default_ranks = {
            "high": 1,
            "planning": 2,
            "spec_qa": 3,
            "low": 4,
            "low_qa": 5,
            "lib": 6,
            "tests": 7,
            "test": 7,
            "qa": 8,
            "coverage": 9,
        }

        role_memo: Dict[str, int] = {}
        visiting: Set[str] = set()

        def _get_role_depth(role: str) -> int:
            if role in role_memo:
                return role_memo[role]
            if role in visiting:
                return 0  # Cycle detected, break cycle gracefully
            visiting.add(role)
            deps = role_deps.get(role, set())
            if not deps:
                depth = 0
            else:
                depth = 1 + max(_get_role_depth(d) for d in deps)
            visiting.remove(role)
            role_memo[role] = depth
            return depth

        for r in role_deps:
            _get_role_depth(r)

        def _role_rank(node: DagNode) -> Tuple[int, int]:
            r = _clean_role(str(node.role_address))
            return (role_memo.get(r, 0), default_ranks.get(r, 999))

        in_deps: Dict[DagNode, Set[DagNode]] = {}
        dependents: Dict[DagNode, Set[DagNode]] = {n: set() for n in reachable}

        for n in reachable:
            deps_in_subgraph = {
                dep.node for dep in storage.get_dependencies(n)
                if dep.node in reachable
            }
            in_deps[n] = deps_in_subgraph
            for dep_node in deps_in_subgraph:
                dependents[dep_node].add(n)

        ready = [n for n in reachable if not in_deps[n]]
        topological_order: List[DagNode] = []

        while ready:
            ready.sort(key=lambda n: (_role_rank(n), str(n.unit_address), str(n.role_address)))
            chosen = ready.pop(0)
            topological_order.append(chosen)

            for dependent in list(dependents[chosen]):
                in_deps[dependent].remove(chosen)
                if not in_deps[dependent]:
                    ready.append(dependent)

        self._topological_order = topological_order

    def is_complete(self) -> bool:
        storage = get_singleton(DagStorage)
        return not any(storage.is_dirty(node) for node in self._topological_order)

    def next_ready_batch(self) -> Sequence[DagNode]:
        storage = get_singleton(DagStorage)
        cfg = get_singleton(dag_config.DagConfig)
        batch_limit = max(1, int(cfg.batch_size))

        start_idx: Optional[int] = None
        for i, node in enumerate(self._topological_order):
            if storage.is_dirty(node):
                deps = [
                    dep.node for dep in storage.get_dependencies(node)
                    if dep.node in self._topological_order
                ]
                if all(not storage.is_dirty(d) for d in deps):
                    start_idx = i
                    break

        if start_idx is None:
            return []

        first_node = self._topological_order[start_idx]
        first_role = first_node.role_address
        batch: List[DagNode] = []

        for idx in range(start_idx, len(self._topological_order)):
            curr = self._topological_order[idx]
            if not storage.is_dirty(curr):
                break
            if curr.role_address != first_role:
                break
            batch.append(curr)
            if len(batch) >= batch_limit:
                break

        return batch

    def record_visit(self, batch: Sequence[DagNode]) -> None:
        cfg = get_singleton(dag_config.DagConfig)
        limit = int(cfg.node_visit_limit)
        for node in batch:
            count = self._visit_counts.get(node, 0) + 1
            self._visit_counts[node] = count
            if count > limit:
                raise RuntimeError(
                    f"Node visit limit exceeded ({limit}) for node '{node.unit_address}:{node.role_address}'"
                )


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        DagSubgraph,
        keys=[DagSubgraph, dag_subgraph.DagSubgraph, InTier[SystemTier]],
        tier=system,
    )

_initialize_ = __initialize__
