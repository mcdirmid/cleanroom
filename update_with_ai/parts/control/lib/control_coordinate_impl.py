# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-12T18:21:04Z
# LAST_CHANGED: 2026-10-11T05:03:57Z
# CHANGE: Track node state with the declared target-state values instead of ad-hoc strings, normalize aliases through the alias manager, disambiguate default targets by workspace path modification time, always register scheduled nodes, and prune uncontracted public members
# CODE_HASH: f96c245b00d8
# COVERAGE_AUDIT: 2026-10-12T18:21:04Z
# QA_AUDIT: 2026-10-12T18:21:04Z
# --- END CLEANROOM METADATA ---

from __future__ import annotations
import os
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleResolutionError,
    Singleton,
    get_default_registry,
    get_singleton,
)
from update_with_ai.parts.agent.lib import (
    agent_file_alias,
    agent_node_config,
    agent_session,
)
from update_with_ai.parts.dag.lib import dag_storage, dag_subgraph
from . import (
    control_attribution,
    control_coordinate,
    control_submit,
    control_verification,
    control_work_scheduler,
)


def _extract_unit_info(node: dag_storage.DagNode) -> Tuple[str, str]:
    """Decomposes a node's unit address into its part directory and unit name."""
    addr = str(node.unit_address).strip()
    if ":" in addr:
        pkg_part, target_part = addr.split(":", 1)
        pkg = pkg_part.lstrip("/").strip()
    elif "/" in addr:
        pkg, target_part = addr.rsplit("/", 1)
        pkg = pkg.lstrip("/").strip()
    else:
        pkg, target_part = "", addr

    role = str(node.role_address).split(":")[-1].strip() if node.role_address else ""
    cfg: Optional[agent_node_config.NodeConfig] = None
    try:
        cfg = get_singleton(agent_node_config.NodeConfig)
    except (LifecycleResolutionError, KeyError, RuntimeError, ValueError):
        cfg = None
    role_defs = getattr(cfg, "role_definitions", {}) if cfg is not None else {}
    known_roles = tuple(role_defs.keys())
    if not known_roles and role:
        known_roles = (role,)

    unit_name = target_part
    changed = True
    while changed:
        changed = False
        for r in known_roles:
            if unit_name.endswith(f"_{r}"):
                unit_name = unit_name[: -len(r) - 1]
                changed = True
                break
    return pkg, unit_name


def _normalize_alias(alias: str) -> str:
    """Normalizes an alias string through the session alias manager."""
    raw = alias.strip()
    try:
        converted = get_singleton(agent_file_alias.AliasManager).convert(raw)
    except (LifecycleResolutionError, KeyError, RuntimeError, ValueError):
        converted = None
    if converted is not None:
        relative = str(getattr(converted, "relative_path", ""))
        if relative:
            return relative
    return raw.lstrip("/")


def _bound_file_path(bound_file: Any) -> str:
    """Resolves the host path text of a declared session bound file."""
    ws_path = getattr(bound_file, "workspace_path", None)
    if ws_path is not None:
        return str(getattr(ws_path, "path", ws_path))
    return str(getattr(bound_file, "relative_path", bound_file))


class SessionCoordinator(control_coordinate.SessionCoordinator, Singleton):
    """Central session control coordinator facade."""

    tier = agent_session.agent_session

    def __init__(self) -> None:
        self._nodes: List[dag_storage.DagNode] = []
        self._node_states: Dict[
            dag_storage.DagNode, control_coordinate.TargetState
        ] = {}
        self._alias_to_node: Dict[str, dag_storage.DagNode] = {}
        self._node_to_alias: Dict[dag_storage.DagNode, str] = {}

    def _populate_node_aliases(self, nodes: Sequence[dag_storage.DagNode]) -> None:
        """Registers the supplied nodes as open targets and indexes their aliases."""
        for n in nodes:
            if n not in self._nodes:
                self._nodes.append(n)
            self._node_states[n] = control_coordinate.TargetState.OPEN

        cfg: Optional[agent_node_config.NodeConfig] = None
        try:
            cfg = get_singleton(agent_node_config.NodeConfig)
        except (LifecycleResolutionError, KeyError, RuntimeError, ValueError):
            cfg = None

        node_infos: Dict[dag_storage.DagNode, Tuple[str, str]] = {}
        unit_counts: Dict[str, int] = {}
        for n in self._nodes:
            pkg, unit_name = _extract_unit_info(n)
            node_infos[n] = (pkg, unit_name)
            unit_counts[unit_name] = unit_counts.get(unit_name, 0) + 1

        for n in self._nodes:
            pkg, unit_name = node_infos[n]
            is_unique_unit = unit_counts.get(unit_name, 0) == 1

            src_alias = None
            if (
                cfg is not None
                and getattr(cfg, "src_file_alias_by_node", None)
                and n in cfg.src_file_alias_by_node
            ):
                src_alias = cfg.src_file_alias_by_node[n]
            elif cfg is not None and getattr(cfg, "read_write_files", None):
                for f in cfg.read_write_files:
                    if getattr(f, "owning_node", None) == n:
                        src_alias = getattr(f, "relative_path", "")
                        break

            display_alias = src_alias or (
                unit_name
                if is_unique_unit
                else (f"{pkg}/{unit_name}" if pkg else unit_name)
            )
            self._node_to_alias[n] = display_alias
            self._alias_to_node[display_alias] = n
            if src_alias:
                self._alias_to_node[src_alias] = n
            pkg_unit = f"{pkg}/{unit_name}" if pkg else unit_name
            self._alias_to_node[pkg_unit] = n
            if is_unique_unit:
                self._alias_to_node[unit_name] = n
            unit_addr = str(n.unit_address).lstrip("/")
            self._alias_to_node[unit_addr] = n
            self._alias_to_node[str(n.unit_address)] = n

    @property
    def open_targets(self) -> Sequence[dag_storage.DagNode]:
        """Sequence of nodes currently in OPEN state."""
        return self._open_nodes()

    def _open_nodes(self) -> List[dag_storage.DagNode]:
        return [
            n
            for n in self._nodes
            if self._node_states.get(n) == control_coordinate.TargetState.OPEN
        ]

    def _get_target_state(self, node: dag_storage.DagNode) -> control_coordinate.TargetState:
        return self._node_states.get(node, control_coordinate.TargetState.OPEN)

    def _set_target_state(
        self, node: dag_storage.DagNode, state: control_coordinate.TargetState
    ) -> None:
        self._node_states[node] = state

    def register_node(
        self,
        node: dag_storage.DagNode,
        alias: str,
        state: control_coordinate.TargetState = control_coordinate.TargetState.OPEN,
    ) -> None:
        self._nodes = [n for n in self._nodes if n.unit_address != "//session:target"]
        if node not in self._nodes:
            self._nodes.append(node)
        self._node_states[node] = control_coordinate.TargetState(state)
        normalized = _normalize_alias(alias)
        raw = alias.strip().lstrip("/")
        self._alias_to_node[normalized] = node
        if raw and raw != normalized:
            self._alias_to_node[raw] = node
        self._node_to_alias[node] = normalized

    def get_node_for_alias(self, alias: str) -> Optional[dag_storage.DagNode]:
        cand = alias.strip()
        if not cand:
            return None
        if cand in self._alias_to_node:
            return self._alias_to_node[cand]
        normalized = _normalize_alias(cand)
        if normalized in self._alias_to_node:
            return self._alias_to_node[normalized]
        for node, registered_alias in self._node_to_alias.items():
            if registered_alias == cand:
                return node

        norm_cand = cand.lstrip("/")
        pkg_cand = norm_cand if "/" in norm_cand else None
        matching_pkg: List[dag_storage.DagNode] = []
        matching_unit: List[dag_storage.DagNode] = []
        for node in self._nodes:
            pkg, unit = _extract_unit_info(node)
            pkg_unit = f"{pkg}/{unit}" if pkg else unit
            if pkg_cand and (pkg_cand == pkg_unit or pkg_unit.endswith("/" + pkg_cand)):
                matching_pkg.append(node)
            if cand == unit or norm_cand == unit:
                matching_unit.append(node)

        if len(matching_pkg) == 1:
            return matching_pkg[0]
        if len(matching_unit) == 1:
            return matching_unit[0]

        matching = [
            node
            for node, reg_alias in self._node_to_alias.items()
            if os.path.basename(reg_alias) == os.path.basename(cand)
            or reg_alias.endswith("/" + norm_cand)
            or norm_cand.endswith("/" + reg_alias.lstrip("/"))
        ]
        return matching[0] if len(matching) == 1 else None

    def get_alias_for_node(self, node: dag_storage.DagNode) -> str:
        alias = self._node_to_alias.get(node)
        if alias:
            return alias
        pkg, unit_name = _extract_unit_info(node)
        return f"{pkg}/{unit_name}" if pkg else unit_name

    def _in_batch_dependencies(
        self, node: dag_storage.DagNode
    ) -> Set[dag_storage.DagNode]:
        deps: Set[dag_storage.DagNode] = set()
        storage = get_singleton(dag_storage.DagStorage)
        for d in storage.get_dependencies(node):
            if d.node in self._node_states and d.node != node:
                deps.add(d.node)
        return deps

    def _get_in_batch_dependents(
        self, node: dag_storage.DagNode
    ) -> Sequence[dag_storage.DagNode]:
        storage = get_singleton(dag_storage.DagStorage)
        dependents = []
        for other in self._nodes:
            if other != node:
                deps = storage.get_dependencies(other)
                if any(dep.node == node for dep in deps):
                    dependents.append(other)
        return dependents

    def reset_nodes(self, nodes: Sequence[dag_storage.DagNode]) -> None:
        """Resets session node tracking to the supplied nodes."""
        self._node_states.clear()
        self._populate_node_aliases(nodes)

    def resolve_default_target(
        self, last_accessed_file: Optional[Any] = None
    ) -> Optional[dag_storage.DagNode]:
        open_nodes = self._open_nodes()
        if not open_nodes:
            return None
        if len(open_nodes) == 1:
            return open_nodes[0]

        open_set = set(open_nodes)
        rw_files: List[Any] = []
        try:
            cfg = get_singleton(agent_node_config.NodeConfig)
            rw_files = list(getattr(cfg, "read_write_files", None) or [])
        except (LifecycleResolutionError, KeyError, RuntimeError, ValueError):
            pass

        def _owning_open_node(f: Any) -> Optional[dag_storage.DagNode]:
            owner = getattr(f, "owning_node", None)
            if owner is not None:
                return owner if owner in open_set else None
            alias_node = self.get_node_for_alias(str(getattr(f, "relative_path", "")))
            return alias_node if alias_node in open_set else None

        last_f = last_accessed_file
        if last_f is not None:
            last_path = getattr(
                last_f, "relative_path", getattr(last_f, "short_name", str(last_f))
            )
            cand_node = self.get_node_for_alias(str(last_path)) or getattr(
                last_f, "owning_node", None
            )
            if cand_node is not None and cand_node in open_set:
                return cand_node

        candidates = [
            (node, _bound_file_path(f))
            for f in rw_files
            for node in [_owning_open_node(f)]
            if node is not None
        ]
        if len({node for node, _ in candidates}) == 1:
            return candidates[0][0]

        latest_node: Optional[dag_storage.DagNode] = None
        latest_mtime = -1.0
        for node, path_text in candidates:
            try:
                mtime = os.path.getmtime(path_text)
            except OSError:
                continue
            if mtime > latest_mtime:
                latest_mtime = mtime
                latest_node = node
        return latest_node

    def dispatch_get_work(
        self,
        subgraph: Optional[dag_subgraph.DagSubgraph] = None,
        dir_scope: Optional[str] = None,
        max_batch_size: Optional[int] = None,
    ) -> control_work_scheduler.WorkSchedule:
        if max_batch_size is not None and max_batch_size <= 0:
            max_batch_size = None
        scheduler = get_singleton(control_work_scheduler.WorkScheduler)
        schedule = scheduler.schedule_work(
            subgraph=subgraph, dir_scope=dir_scope, max_batch_size=max_batch_size
        )
        role_cfg = get_singleton(agent_node_config.RoleConfig)

        tasks = list(schedule.tasks)
        storage = get_singleton(dag_storage.DagStorage)

        for task in tasks:
            if hasattr(storage, "materialize_template"):
                storage.materialize_template(task.node)
        self._populate_node_aliases([task.node for task in tasks])
        role_cfg.set_nodes([task.node for task in tasks])
        return control_work_scheduler.WorkSchedule(tasks=tasks)

    def dispatch_check_files(
        self, target_alias: Optional[str] = None
    ) -> control_verification.VerificationResult:
        evaluator = get_singleton(control_verification.VerificationEvaluator)
        if target_alias:
            node = self.get_node_for_alias(target_alias)
            if node is not None:
                return evaluator.evaluate_verification(target=node)
        open_targets = self._open_nodes()
        if not open_targets:
            return evaluator.evaluate_verification(target=None)
        results = [evaluator.evaluate_verification(target=node) for node in open_targets]
        all_passed = all(result.passed for result in results)
        all_cached = all(result.is_cached for result in results)
        diagnostic = "\n".join(
            result.diagnostic_output for result in results if result.diagnostic_output
        ).strip()
        if all_passed and not diagnostic:
            diagnostic = "All open targets verified successfully."
        return control_verification.VerificationResult(
            passed=all_passed,
            diagnostic_output=diagnostic,
            is_cached=all_cached,
        )

    def dispatch_submit(
        self,
        target_alias: Optional[str] = None,
        change_summary: Optional[str] = None,
        has_modifications: bool = False,
    ) -> control_coordinate.ControlDispatchOutcome:
        target_node = (
            self.get_node_for_alias(target_alias)
            if target_alias
            else self.resolve_default_target()
        )
        if (
            target_node is None
            or self._get_target_state(target_node)
            != control_coordinate.TargetState.OPEN
        ):
            open_list = ", ".join(f"`{self.get_alias_for_node(n)}`" for n in self._open_nodes())
            message = (
                f"Error: Target '{target_alias or ''}' is not an open target. "
                f"Available: {open_list}"
            )
            return control_coordinate.ControlDispatchOutcome(
                success=False, message=message, remaining_open_targets=self._open_nodes()
            )

        submit_coord = get_singleton(control_submit.SubmissionCoordinator)
        outcome = submit_coord.submit_target(
            target_node=target_node,
            change_summary=change_summary,
            has_modifications=has_modifications,
            in_batch_dependencies=list(self._in_batch_dependencies(target_node)),
        )
        if outcome.accepted:
            self._set_target_state(target_node, control_coordinate.TargetState.CLEAN)
        return control_coordinate.ControlDispatchOutcome(
            success=outcome.accepted,
            message=outcome.message,
            remaining_open_targets=self._open_nodes(),
        )

    def dispatch_blame(
        self,
        source_alias: Optional[str] = None,
        blame_target_alias: Optional[str] = None,
        explanation: str = "",
    ) -> control_coordinate.ControlDispatchOutcome:
        source_node = (
            self.get_node_for_alias(source_alias)
            if source_alias
            else self.resolve_default_target()
        )
        if source_node is None:
            open_list = ", ".join(f"`{self.get_alias_for_node(n)}`" for n in self._open_nodes())
            return control_coordinate.ControlDispatchOutcome(
                success=False,
                message=f"Error: No open target found for blame. Available: {open_list}",
                remaining_open_targets=self._open_nodes(),
            )

        blame_target_node = (
            self.get_node_for_alias(blame_target_alias) if blame_target_alias else None
        )
        if blame_target_node is None:
            return control_coordinate.ControlDispatchOutcome(
                success=False,
                message=(
                    f"Error: Blame target '{blame_target_alias or ''}' could not be "
                    f"resolved."
                ),
                remaining_open_targets=self._open_nodes(),
            )

        outcome = get_singleton(control_attribution.AttributionCoordinator).blame_target(
            source_node=source_node,
            blame_target_node=blame_target_node,
            explanation=explanation,
            in_batch_dependencies=list(self._in_batch_dependencies(source_node)),
            in_batch_dependents=self._get_in_batch_dependents(source_node),
        )
        if outcome.accepted:
            self._set_target_state(
                source_node, control_coordinate.TargetState.ATTRIBUTED
            )
            for affected in outcome.affected_nodes:
                if affected != source_node:
                    self._set_target_state(
                        affected, control_coordinate.TargetState.FAILED
                    )
        return control_coordinate.ControlDispatchOutcome(
            success=outcome.accepted,
            message=outcome.message,
            remaining_open_targets=self._open_nodes(),
        )

    def dispatch_fail(
        self,
        target_alias: Optional[str] = None,
        explanation: str = "",
    ) -> control_coordinate.ControlDispatchOutcome:
        target_node = (
            self.get_node_for_alias(target_alias)
            if target_alias
            else self.resolve_default_target()
        )
        if target_node is None:
            open_list = ", ".join(f"`{self.get_alias_for_node(n)}`" for n in self._open_nodes())
            return control_coordinate.ControlDispatchOutcome(
                success=False,
                message=f"Error: No open target found to fail. Available: {open_list}",
                remaining_open_targets=self._open_nodes(),
            )

        outcome = get_singleton(control_attribution.AttributionCoordinator).fail_target(
            target_node=target_node,
            explanation=explanation,
            in_batch_dependents=self._get_in_batch_dependents(target_node),
        )
        if outcome.accepted:
            for affected in outcome.affected_nodes:
                self._set_target_state(affected, control_coordinate.TargetState.FAILED)
        return control_coordinate.ControlDispatchOutcome(
            success=outcome.accepted,
            message=outcome.message,
            remaining_open_targets=self._open_nodes(),
        )


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        SessionCoordinator,
        keys=[SessionCoordinator, control_coordinate.SessionCoordinator],
        tier=SessionCoordinator.tier,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
