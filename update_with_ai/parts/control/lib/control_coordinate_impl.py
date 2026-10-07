# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T00:13:59Z
# LAST_CHANGED: 2026-10-06T11:45:00Z
# CHANGE: handle optional and mock NodeConfig safely
# CODE_HASH: 1f31c78d15ad
# COVERAGE_AUDIT: 2026-10-07T00:13:59Z
# QA_AUDIT: 2026-10-07T00:13:59Z
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
    KNOWN_ROLES = (
        "grounding_qa",
        "coverage",
        "qa",
        "grounding",
        "planning",
        "high",
        "low",
        "test",
        "lib",
    )
    unit_name = target_part
    if role and unit_name.endswith(f"_{role}"):
        unit_name = unit_name[: -len(f"_{role}")]
    elif any(unit_name.endswith(f"_{r}") for r in KNOWN_ROLES):
        for r in KNOWN_ROLES:
            if unit_name.endswith(f"_{r}"):
                unit_name = unit_name[: -len(f"_{r}")]
                break
    if role in ("qa", "coverage", "grounding_qa"):
        for dep_role in ("lib", "test", "grounding"):
            if unit_name.endswith(f"_{dep_role}"):
                unit_name = unit_name[: -len(f"_{dep_role}")]
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

    def _ensure_nodes(self) -> None:
        if self._nodes:
            return
        cfg: Optional[agent_node_config.NodeConfig] = None
        try:
            cfg = get_singleton(agent_node_config.NodeConfig)
        except (LifecycleResolutionError, KeyError, RuntimeError, ValueError):
            cfg = None

        collected: List[dag_storage.DagNode] = []
        try:
            role_cfg = get_singleton(agent_node_config.RoleConfig)
            if role_cfg.nodes:
                collected.extend([n for n in role_cfg.nodes if n not in collected])
        except (LifecycleResolutionError, KeyError, RuntimeError, ValueError):
            pass

        if not collected and cfg is not None and getattr(cfg, "src_file_alias_by_node", None):
            collected.extend([n for n in cfg.src_file_alias_by_node if n not in collected])

        if not collected and cfg is not None and getattr(cfg, "read_write_files", None):
            for f in sorted(cfg.read_write_files, key=lambda x: getattr(x, "relative_path", getattr(x, "short_name", ""))):
                owner = getattr(f, "owning_node", None)
                if owner is not None and owner not in collected:
                    collected.append(owner)

        if not collected:
            has_role = False
            try:
                role_cfg = get_singleton(agent_node_config.RoleConfig)
                has_role = bool(getattr(role_cfg, "role", None))
            except (LifecycleResolutionError, KeyError, RuntimeError, ValueError):
                pass
            if not has_role:
                dummy_node = dag_storage.DagNode(
                    unit_address=dag_storage.UnitAddress("//session:target"),
                    role_address=dag_storage.RoleAddress(""),
                )
                collected.append(dummy_node)

        self._populate_node_aliases(collected)

    def _populate_node_aliases(self, nodes: Sequence[dag_storage.DagNode]) -> None:
        self._nodes = list(nodes)
        self._node_states = {n: "OPEN" for n in self._nodes}
        self._alias_to_node = {}
        self._node_to_alias = {}
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
            self._node_states[n] = "OPEN"
            self._alias_to_node[display_alias] = n
            if src_alias:
                self._alias_to_node[src_alias] = n
            pkg_unit = f"{pkg}/{unit_name}" if pkg else unit_name
            self._alias_to_node[pkg_unit] = n
            if is_unique_unit:
                self._alias_to_node[unit_name] = n

    @property
    def nodes(self) -> Sequence[dag_storage.DagNode]:
        self._ensure_nodes()
        return self._nodes

    @property
    def is_multi_node(self) -> bool:
        self._ensure_nodes()
        return len(self._nodes) > 1

    @property
    def open_targets(self) -> Sequence[dag_storage.DagNode]:
        """Sequence of nodes currently in OPEN state."""
        self._ensure_nodes()
        return [n for n in self._nodes if self._node_states.get(n) == "OPEN"]

    def open_nodes(self) -> List[dag_storage.DagNode]:
        return list(self.open_targets)

    def register_node(
        self,
        node: dag_storage.DagNode,
        alias: str,
        state: control_coordinate.TargetState | str = "OPEN",
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
        self._ensure_nodes()
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
        self._ensure_nodes()
        alias = self._node_to_alias.get(node)
        if alias:
            return alias
        pkg, unit_name = _extract_unit_info(node)
        return f"{pkg}/{unit_name}" if pkg else unit_name

    def get_target_state(self, node: dag_storage.DagNode) -> str:
        self._ensure_nodes()
        return self._node_states.get(node, "OPEN")

    get_node_state = get_target_state

    def set_target_state(self, node: dag_storage.DagNode, state: str) -> None:
        self._ensure_nodes()
        self._node_states[node] = state

    set_node_state = set_target_state

    def is_clean_in_turn(self, node: dag_storage.DagNode) -> bool:
        self._ensure_nodes()
        return node in self._cleaned_in_turn or self.get_target_state(node) == "SUBMITTED"

    def mark_clean_in_turn(self, node: dag_storage.DagNode) -> None:
        self._ensure_nodes()
        self._cleaned_in_turn.add(node)

    def get_in_batch_dependencies(self, node: dag_storage.DagNode) -> Set[dag_storage.DagNode]:
        self._ensure_nodes()
        deps: Set[dag_storage.DagNode] = set()
        storage = get_singleton(dag_storage.DagStorage)
        for d in storage.get_dependencies(node):
            if d.node in self._node_states and d.node != node:
                deps.add(d.node)
        return deps

    def get_in_session_dependencies(self, node: dag_storage.DagNode) -> Set[dag_storage.DagNode]:
        return self.get_in_batch_dependencies(node)

    def _get_in_batch_dependents(self, node: dag_storage.DagNode) -> Sequence[dag_storage.DagNode]:
        self._ensure_nodes()
        storage = get_singleton(dag_storage.DagStorage)
        dependents = []
        for other in self._nodes:
            if other != node:
                deps = storage.get_dependencies(other)
                if any(dep.node == node for dep in deps):
                    dependents.append(other)
        return dependents

    def fail_dependents(self, node: dag_storage.DagNode) -> None:
        self._ensure_nodes()
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
        if not self._nodes:
            self._ensure_nodes()

    def format_open_targets_reminder(self) -> str:
        open_n = self.open_nodes()
        if not open_n:
            return ""
        items = "\n".join(f"- `{self.get_alias_for_node(n)}`" for n in open_n)
        return f"Remaining submit targets to handle:\n{items}"

    def resolve_default_target(
        self, last_accessed_file: Optional[Any] = None
    ) -> Optional[dag_storage.DagNode]:
        self._ensure_nodes()
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
        scheduler = get_singleton(control_work_scheduler.WorkScheduler)
        schedule = scheduler.schedule_work(
            subgraph=subgraph, dir_scope=dir_scope, max_batch_size=max_batch_size
        )
        for task in schedule.tasks:
            self.register_node(task.node, alias=task.node.unit_address, state="OPEN")
        return schedule

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
