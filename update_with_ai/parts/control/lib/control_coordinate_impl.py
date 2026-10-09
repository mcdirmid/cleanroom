# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:47:23Z
# LAST_CHANGED: 2026-10-09T22:20:00Z
# CHANGE: Populate session targets and aliases strictly from scheduled work during dispatch_get_work
# CODE_HASH: 17876f079fc3
# QA_AUDIT: 2026-10-09T21:47:23Z
# --- END CLEANROOM METADATA ---

from __future__ import annotations
import os
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
from support.lib.lifecycle import LifecycleResolutionError, Singleton, get_singleton
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
    cfg = get_singleton(agent_node_config.NodeConfig)
    role_defs = getattr(cfg, "role_definitions", {})
    known_roles = tuple(set(role_defs.keys()) | {"lib", "low", "planning", "high", "grounding", "spec", "qa", "coverage", "test"})

    unit_name = target_part
    changed = True
    while changed:
        changed = False
        for r in known_roles:
            if unit_name.endswith(f"_{r}"):
                unit_name = unit_name[: -len(f"_{r}")]
                changed = True
                break
    return pkg, unit_name


class SessionCoordinator(control_coordinate.SessionCoordinator, Singleton):
    """Central session control coordinator facade."""

    tier = agent_session.agent_session

    def __init__(self) -> None:
        self._nodes: List[dag_storage.DagNode] = []
        self._node_states: Dict[dag_storage.DagNode, str] = {}
        self._alias_to_node: Dict[str, dag_storage.DagNode] = {}
        self._node_to_alias: Dict[dag_storage.DagNode, str] = {}
        self._cleaned_in_turn: Set[dag_storage.DagNode] = set()



    def _populate_node_aliases(self, nodes: Sequence[dag_storage.DagNode]) -> None:
        for n in nodes:
            if n not in self._nodes:
                self._nodes.append(n)
            self._node_states[n] = "OPEN"
        self._cleaned_in_turn = set()

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
            if cfg is not None and getattr(cfg, "src_file_alias_by_node", None) and n in cfg.src_file_alias_by_node:
                src_alias = cfg.src_file_alias_by_node[n]
            elif cfg is not None and getattr(cfg, "read_write_files", None):
                for f in cfg.read_write_files:
                    if hasattr(f, "owning_node") and f.owning_node == n:
                        src_alias = getattr(f, "relative_path", "")
                        break

            display_alias = src_alias or (unit_name if is_unique_unit else (f"{pkg}/{unit_name}" if pkg else unit_name))
            self._node_to_alias[n] = display_alias
            self._alias_to_node[display_alias] = n
            if src_alias:
                self._alias_to_node[src_alias] = n
            pkg_unit = f"{pkg}/{unit_name}" if pkg else unit_name
            self._alias_to_node[pkg_unit] = n
            if is_unique_unit:
                self._alias_to_node[unit_name] = n
            unit_addr = n.unit_address.lstrip("/")
            self._alias_to_node[unit_addr] = n
            self._alias_to_node[n.unit_address] = n

    @property
    def nodes(self) -> Sequence[dag_storage.DagNode]:
        return self._nodes

    @property
    def is_multi_node(self) -> bool:
        return len(self._nodes) > 1

    @property
    def open_targets(self) -> Sequence[dag_storage.DagNode]:
        """Sequence of nodes currently in OPEN state."""
        return [n for n in self._nodes if self._node_states.get(n) == "OPEN"]

    def open_nodes(self) -> List[dag_storage.DagNode]:
        return list(self.open_targets)

    def register_node(
        self,
        node: dag_storage.DagNode,
        alias: str,
        state: control_coordinate.TargetState = control_coordinate.TargetState.OPEN,
    ) -> None:
        self._initialized_nodes = True
        self._nodes = [n for n in self._nodes if n.unit_address != "//session:target"]
        if node not in self._nodes:
            self._nodes.append(node)
        self._node_states[node] = str(state.value if isinstance(state, control_coordinate.TargetState) else state)
        clean_alias = alias.strip().lstrip("/")
        self._alias_to_node[clean_alias] = node
        self._node_to_alias[node] = clean_alias

    def get_node_for_alias(self, alias: str) -> Optional[dag_storage.DagNode]:
        cand = alias.strip()
        if not cand:
            return None
        if cand in self._alias_to_node:
            return self._alias_to_node[cand]
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
            node for node, reg_alias in self._node_to_alias.items()
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

    def get_target_state(self, node: dag_storage.DagNode) -> str:
        return self._node_states.get(node, "OPEN")

    get_node_state = get_target_state

    def set_target_state(self, node: dag_storage.DagNode, state: str) -> None:
        self._node_states[node] = state

    set_node_state = set_target_state

    def is_clean_in_turn(self, node: dag_storage.DagNode) -> bool:
        return node in self._cleaned_in_turn or self.get_target_state(node) == "SUBMITTED"

    def mark_clean_in_turn(self, node: dag_storage.DagNode) -> None:
        self._cleaned_in_turn.add(node)

    def get_in_batch_dependencies(self, node: dag_storage.DagNode) -> Set[dag_storage.DagNode]:
        deps: Set[dag_storage.DagNode] = set()
        storage = get_singleton(dag_storage.DagStorage)
        for d in storage.get_dependencies(node):
            if d.node in self._node_states and d.node != node:
                deps.add(d.node)
        return deps

    def get_in_session_dependencies(self, node: dag_storage.DagNode) -> Set[dag_storage.DagNode]:
        return self.get_in_batch_dependencies(node)

    def _get_in_batch_dependents(self, node: dag_storage.DagNode) -> Sequence[dag_storage.DagNode]:
        storage = get_singleton(dag_storage.DagStorage)
        dependents = []
        for other in self._nodes:
            if other != node:
                deps = storage.get_dependencies(other)
                if any(dep.node == node for dep in deps):
                    dependents.append(other)
        return dependents

    def fail_dependents(self, node: dag_storage.DagNode) -> None:
        to_check = [node]
        while to_check:
            curr = to_check.pop(0)
            for n in self._nodes:
                if self.get_target_state(n) == "OPEN" and curr in self.get_in_batch_dependencies(n):
                    self.set_target_state(n, "FAILED")
                    to_check.append(n)

    def block_dependents(self, node: dag_storage.DagNode) -> None:
        self.fail_dependents(node)

    def reset_nodes(self, nodes: Sequence[dag_storage.DagNode]) -> None:
        self._node_states.clear()
        self._cleaned_in_turn.clear()
        self._populate_node_aliases(nodes)

    def format_open_targets_reminder(self) -> str:
        open_n = self.open_nodes()
        if not open_n:
            return ""
        items = "\n".join(f"- `{self.get_alias_for_node(n)}`" for n in open_n)
        return f"Remaining submit targets to handle:\n{items}"

    def resolve_default_target(
        self, last_accessed_file: Optional[Any] = None
    ) -> Optional[dag_storage.DagNode]:
        open_nodes = self.open_nodes()
        if not open_nodes:
            return None
        if len(open_nodes) == 1:
            return open_nodes[0]

        rw_files = []
        try:
            cfg = get_singleton(agent_node_config.NodeConfig)
            rw_files = getattr(cfg, "read_write_files", None) or []
        except (LifecycleResolutionError, KeyError, RuntimeError, ValueError):
            pass

        def _is_file_open(f: Any) -> bool:
            owner = getattr(f, "owning_node", None)
            if owner is not None and self.get_target_state(owner) != "OPEN":
                return False
            alias_node = self.get_node_for_alias(getattr(f, "relative_path", ""))
            return not (alias_node is not None and self.get_target_state(alias_node) != "OPEN")

        unsubmitted = [f for f in rw_files if _is_file_open(f)]
        if len(unsubmitted) == 1:
            f = unsubmitted[0]
            node = getattr(f, "owning_node", None) or self.get_node_for_alias(getattr(f, "relative_path", str(f)))
            return node if node is not None and node in open_nodes else open_nodes[0]

        last_f = last_accessed_file
        if last_f is not None:
            last_path = getattr(last_f, "relative_path", getattr(last_f, "short_name", str(last_f)))
            cand_node = self.get_node_for_alias(last_path) or getattr(last_f, "owning_node", None)
            if cand_node is not None and self.get_target_state(cand_node) == "OPEN":
                if not rw_files or any(
                    (f == last_f or getattr(f, "relative_path", "") == last_path) for f in unsubmitted
                ):
                    return cand_node

        return None

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
        if hasattr(role_cfg, "set_nodes"):
            role_cfg.set_nodes([task.node for task in tasks])
        return control_work_scheduler.WorkSchedule(tasks=tasks)

    def dispatch_check_files(
        self, target_alias: Optional[str] = None
    ) -> control_verification.VerificationResult:
        evaluator = get_singleton(control_verification.VerificationEvaluator)
        if target_alias:
            node = self.get_node_for_alias(target_alias)
            return evaluator.evaluate_verification(target=node)
        open_n = self.open_targets
        if not open_n:
            return evaluator.evaluate_verification(target=None)
        results = [evaluator.evaluate_verification(target=node) for node in open_n]
        all_passed = all(r.passed for r in results)
        all_cached = all(r.is_cached for r in results)
        diag = "\n".join(r.diagnostic_output for r in results if r.diagnostic_output).strip()
        if all_passed and not diag:
            diag = "All open targets verified successfully."
        return control_verification.VerificationResult(passed=all_passed, diagnostic_output=diag, is_cached=all_cached)

    def dispatch_submit(
        self,
        target_alias: Optional[str] = None,
        change_summary: Optional[str] = None,
        has_modifications: bool = False,
    ) -> control_coordinate.ControlDispatchOutcome:
        target_node = self.get_node_for_alias(target_alias) if target_alias else self.resolve_default_target()
        if target_node is None or self.get_target_state(target_node) != "OPEN":
            open_list = ", ".join(f"`{self.get_alias_for_node(n)}`" for n in self.open_targets)
            msg = f"Error: Target '{target_alias or ''}' is not an open target. Available: {open_list}"
            return control_coordinate.ControlDispatchOutcome(success=False, message=msg, remaining_open_targets=self.open_targets)

        in_batch_deps = list(self.get_in_batch_dependencies(target_node))
        submit_coord = get_singleton(control_submit.SubmissionCoordinator)
        outcome = submit_coord.submit_target(
            target_node=target_node,
            change_summary=change_summary,
            has_modifications=has_modifications,
            in_batch_dependencies=in_batch_deps,
        )
        if outcome.accepted:
            self.set_target_state(target_node, "SUBMITTED")
            self.mark_clean_in_turn(target_node)
        return control_coordinate.ControlDispatchOutcome(success=outcome.accepted, message=outcome.message, remaining_open_targets=self.open_targets)

    def dispatch_blame(
        self,
        source_alias: Optional[str] = None,
        blame_target_alias: Optional[str] = None,
        explanation: str = "",
    ) -> control_coordinate.ControlDispatchOutcome:
        source_node = self.get_node_for_alias(source_alias) if source_alias else self.resolve_default_target()
        if source_node is None:
            open_list = ", ".join(f"`{self.get_alias_for_node(n)}`" for n in self.open_targets)
            return control_coordinate.ControlDispatchOutcome(success=False, message=f"Error: No open target found for blame. Available: {open_list}", remaining_open_targets=self.open_targets)

        blame_target_node = self.get_node_for_alias(blame_target_alias) if blame_target_alias else None
        if blame_target_node is None:
            return control_coordinate.ControlDispatchOutcome(success=False, message=f"Error: Blame target '{blame_target_alias or ''}' could not be resolved.", remaining_open_targets=self.open_targets)

        in_batch_deps = list(self.get_in_batch_dependencies(source_node))
        in_batch_dependents = self._get_in_batch_dependents(source_node)
        attrib_coord = get_singleton(control_attribution.AttributionCoordinator)
        outcome = attrib_coord.blame_target(
            source_node=source_node,
            blame_target_node=blame_target_node,
            explanation=explanation,
            in_batch_dependencies=in_batch_deps,
            in_batch_dependents=in_batch_dependents,
        )
        if outcome.accepted:
            self.set_target_state(source_node, "BLAME")
            for aff in outcome.affected_nodes:
                if aff != source_node:
                    self.set_target_state(aff, "FAILED")
        return control_coordinate.ControlDispatchOutcome(success=outcome.accepted, message=outcome.message, remaining_open_targets=self.open_targets)

    def dispatch_fail(
        self,
        target_alias: Optional[str] = None,
        explanation: str = "",
    ) -> control_coordinate.ControlDispatchOutcome:
        target_node = self.get_node_for_alias(target_alias) if target_alias else self.resolve_default_target()
        if target_node is None:
            open_list = ", ".join(f"`{self.get_alias_for_node(n)}`" for n in self.open_targets)
            return control_coordinate.ControlDispatchOutcome(success=False, message=f"Error: No open target found to fail. Available: {open_list}", remaining_open_targets=self.open_targets)

        in_batch_dependents = self._get_in_batch_dependents(target_node)
        attrib_coord = get_singleton(control_attribution.AttributionCoordinator)
        outcome = attrib_coord.fail_target(
            target_node=target_node,
            explanation=explanation,
            in_batch_dependents=in_batch_dependents,
        )
        if outcome.accepted:
            for aff in outcome.affected_nodes:
                self.set_target_state(aff, "FAILED")
        return control_coordinate.ControlDispatchOutcome(success=outcome.accepted, message=outcome.message, remaining_open_targets=self.open_targets)
