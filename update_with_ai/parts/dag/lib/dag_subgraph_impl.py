# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T00:13:59Z
# LAST_CHANGED: 2026-10-06T11:00:00Z
# CHANGE: compute role tiers dynamically from graph dependencies
# CODE_HASH: 1a3468b7016e
# COVERAGE_AUDIT: 2026-10-07T00:13:59Z
# QA_AUDIT: 2026-10-07T00:13:59Z
# --- END CLEANROOM METADATA ---

# Requirements specified in dag_subgraph_impl.pyi
from collections import deque
from typing import Dict, List, Optional, Sequence, Set
from . import dag_config
from . import dag_storage
from . import dag_subgraph
from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    get_singleton,
    system,
)


def _compute_role_tiers(
    nodes: Set[dag_storage.DagNode], storage: dag_storage.DagStorage
) -> Dict[str, int]:
    role_deps: Dict[str, Set[str]] = {}
    all_roles: Set[str] = set()

    for n in sorted(nodes, key=lambda x: (x.unit_address, x.role_address)):
        r_name = (
            str(n.role_address).split(":")[-1].strip().lower()
            if ":" in str(n.role_address)
            else str(n.role_address).strip().lower()
        )
        all_roles.add(r_name)
        if r_name not in role_deps:
            role_deps[r_name] = set()
        for dep in sorted(
            storage.get_dependencies(n),
            key=lambda d: (d.node.unit_address, d.node.role_address),
        ):
            if dep.node in nodes:
                dep_r = (
                    str(dep.node.role_address).split(":")[-1].strip().lower()
                    if ":" in str(dep.node.role_address)
                    else str(dep.node.role_address).strip().lower()
                )
                all_roles.add(dep_r)
                if dep_r != r_name:
                    role_deps[r_name].add(dep_r)

    memo: Dict[str, int] = {}
    visiting: Set[str] = set()

    def _get_depth(role: str) -> int:
        if role in memo:
            return memo[role]
        if role in visiting:
            return 0
        visiting.add(role)
        deps = role_deps.get(role, set())
        if not deps:
            depth = 0
        else:
            depth = 1 + max(_get_depth(d) for d in sorted(deps))
        visiting.remove(role)
        memo[role] = depth
        return depth

    for r in sorted(all_roles):
        _get_depth(r)

    return memo


def _role_tier(role_address: str, role_tiers: Optional[Dict[str, int]] = None) -> int:
    name = (
        role_address.split(":")[-1].strip().lower()
        if ":" in role_address
        else role_address.strip().lower()
    )
    if role_tiers is not None:
        return role_tiers.get(name, 0)
    return 0


def _node_sort_key(
    n: dag_storage.DagNode, role_tiers: Optional[Dict[str, int]] = None
) -> tuple[int, str, str]:
    return (_role_tier(n.role_address, role_tiers), n.unit_address, n.role_address)


class DagSubgraph(dag_subgraph.DagSubgraph, Singleton):
    tier = system

    def __init__(self) -> None:
        self._target: Optional[dag_storage.DagNode] = None
        self._nodes: Set[dag_storage.DagNode] = set()
        self._role_tiers: Dict[str, int] = {}
        self._order: List[dag_storage.DagNode] = []
        self._visits: Dict[dag_storage.DagNode, int] = {}

    def _collect_subgraph(
        self, root: dag_storage.DagNode, storage: dag_storage.DagStorage
    ) -> Set[dag_storage.DagNode]:
        visited: Set[dag_storage.DagNode] = set()
        queue: deque[dag_storage.DagNode] = deque([root])
        while queue:
            curr = queue.popleft()
            if curr not in visited:
                visited.add(curr)
                for dep in storage.get_dependencies(curr):
                    queue.append(dep.node)
        return visited

    def _topological_sort(
        self,
        nodes: Set[dag_storage.DagNode],
        storage: dag_storage.DagStorage,
        role_tiers: Dict[str, int],
    ) -> List[dag_storage.DagNode]:
        def sort_key(n: dag_storage.DagNode) -> tuple[int, str, str]:
            return _node_sort_key(n, role_tiers)

        sorted_nodes = sorted(nodes, key=sort_key)
        in_degree: Dict[dag_storage.DagNode, int] = {n: 0 for n in sorted_nodes}
        adj: Dict[dag_storage.DagNode, List[dag_storage.DagNode]] = {
            n: [] for n in sorted_nodes
        }

        for n in sorted_nodes:
            for dep in sorted(
                storage.get_dependencies(n), key=lambda d: sort_key(d.node)
            ):
                if dep.node in nodes:
                    adj[dep.node].append(n)
                    in_degree[n] += 1

        generation: Dict[dag_storage.DagNode, int] = {n: 0 for n in sorted_nodes}

        ready = sorted(
            [n for n, deg in in_degree.items() if deg == 0],
            key=lambda n: (generation[n], sort_key(n)),
        )
        order: List[dag_storage.DagNode] = []

        while ready:
            curr = ready.pop(0)
            order.append(curr)
            newly_ready = []
            for neighbor in adj[curr]:
                generation[neighbor] = max(
                    generation[neighbor], generation[curr] + 1
                )
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    newly_ready.append(neighbor)
            for nr in newly_ready:
                ready.append(nr)
            ready.sort(key=lambda n: (generation[n], sort_key(n)))

        return order

    def set_target(self, target: dag_storage.DagNode) -> None:
        storage = get_singleton(dag_storage.DagStorage)
        self._target = target
        self._nodes = self._collect_subgraph(target, storage)
        self._role_tiers = _compute_role_tiers(self._nodes, storage)
        self._order = self._topological_sort(self._nodes, storage, self._role_tiers)
        self._visits = {n: 0 for n in self._nodes}

    def is_complete(self) -> bool:
        if (
            self._target is None or not self._nodes
        ):  # pragma: no cover (assumption: target set before completion check)
            return False
        storage = get_singleton(dag_storage.DagStorage)
        return not any(storage.is_dirty(n) for n in self._nodes)

    def next_ready_batch(self) -> Sequence[dag_storage.DagNode]:
        storage = get_singleton(dag_storage.DagStorage)
        cfg = get_singleton(dag_config.DagConfig)
        batch_size = max(1, cfg.batch_size)

        ready_candidates: List[dag_storage.DagNode] = []
        for curr in self._order:
            if not storage.is_dirty(curr):
                continue

            deps_clean = all(
                not storage.is_dirty(d.node)
                for d in storage.get_dependencies(curr)
                if d.node in self._nodes
            )
            if deps_clean:
                ready_candidates.append(curr)

        if not ready_candidates:
            return []

        best_tier = min(
            _role_tier(c.role_address, self._role_tiers) for c in ready_candidates
        )
        curr = next(
            c
            for c in ready_candidates
            if _role_tier(c.role_address, self._role_tiers) == best_tier
        )

        batch: List[dag_storage.DagNode] = [curr]
        batch_set: Set[dag_storage.DagNode] = {curr}

        dirty_order = [n for n in self._order if storage.is_dirty(n)]
        curr_idx = dirty_order.index(curr)
        if batch_size > 1:
            for cand in dirty_order[curr_idx + 1 :]:
                if len(batch) >= batch_size:
                    break
                if cand.role_address != curr.role_address:
                    break
                cand_deps_clean = all(
                    d.node in batch_set or not storage.is_dirty(d.node)
                    for d in storage.get_dependencies(cand)
                    if d.node in self._nodes
                )
                if not cand_deps_clean:
                    break
                batch.append(cand)
                batch_set.add(cand)

        return batch

    def record_visit(self, batch: Sequence[dag_storage.DagNode]) -> None:
        cfg = get_singleton(dag_config.DagConfig)
        limit = cfg.node_visit_limit

        for node in batch:
            count = self._visits.get(node, 0) + 1
            self._visits[node] = count
            if count > limit:
                raise RuntimeError(
                    f"Node ({node.unit_address}, {node.role_address}) exceeded node visit limit of {limit}"
                )


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        DagSubgraph,
        keys=[DagSubgraph, dag_subgraph.DagSubgraph],
        tier=system,
    )
