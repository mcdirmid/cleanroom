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
    file_alias,
    node_config,
    agent_session,
)
from update_with_ai.parts.dag.lib import dag_storage, subgraph
from . import (
    attribution,
    coordinate,
    submit,
    verification,
    work_scheduler,
)


def _get_role_definitions() -> Dict[str, Any]:
    """Retrieves declared role definitions from NodeConfig or WorkspaceRegistry."""
    try:
        cfg: Any = get_singleton(node_config.NodeConfig)
        if cfg is not None and hasattr(cfg, "role_definitions"):
            r_defs = cfg.role_definitions
            if isinstance(r_defs, dict) and r_defs:
                return r_defs
    except (LifecycleResolutionError, KeyError, AttributeError, RuntimeError):
        pass

    try:
        from update_with_ai.parts.workspace.lib import role_registry
        reg = get_singleton(role_registry.WorkspaceRegistry)
        return {r.role_name: r for r in reg.list_roles()}
    except Exception:
        pass

    return {}


def _role_src_pattern(role_def: Any) -> str:
    """Returns the source pattern for a role definition or mapping."""
    if hasattr(role_def, "src_pattern"):
        return str(role_def.src_pattern or "")
    if isinstance(role_def, dict):
        return str(role_def.get("src_pattern") or "")
    return ""


def _role_name(role_def: Any, default: str = "") -> str:
    """Returns the role name for a role definition or mapping."""
    if hasattr(role_def, "role_name"):
        return str(role_def.role_name or default)
    if isinstance(role_def, dict):
        return str(role_def.get("role_name") or default)
    return default


def _role_audit_tag(role_def: Any) -> Optional[str]:
    """Returns the audit tag for a role definition or mapping."""
    if hasattr(role_def, "audit_tag"):
        return role_def.audit_tag
    if isinstance(role_def, dict):
        return role_def.get("audit_tag")
    return None


def _role_feedback_deps(role_def: Any) -> Sequence[str]:
    """Returns the feedback role dependencies for a role definition or mapping."""
    if hasattr(role_def, "feedback_role_deps"):
        return role_def.feedback_role_deps or ()
    if isinstance(role_def, dict):
        return role_def.get("feedback_role_deps") or ()
    return ()


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
    role_defs = _get_role_definitions()
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
        converted = get_singleton(file_alias.AliasManager).to_alias(raw)
    except (LifecycleResolutionError, KeyError, RuntimeError, ValueError):
        converted = None
    if converted is not None:
        relative = str(converted.relative_path if hasattr(converted, "relative_path") else "")
        if relative:
            return relative
    return raw.lstrip("/")


def _bound_file_path(bound_file: Any) -> str:
    """Resolves the host path text of a declared session bound file."""
    if hasattr(bound_file, "workspace_path") and bound_file.workspace_path is not None:
        ws_path = bound_file.workspace_path
        return str(ws_path.path if hasattr(ws_path, "path") else ws_path)
    if hasattr(bound_file, "relative_path"):
        return str(bound_file.relative_path)
    return str(bound_file)


def _node_display_alias(node: dag_storage.DagNode) -> str:
    """Returns a user/agent-facing file alias for a node, avoiding raw Bazel target addresses."""
    try:
        cfg = get_singleton(node_config.NodeConfig)
        if cfg is not None:
            if hasattr(cfg, "src_file_alias_by_node") and cfg.src_file_alias_by_node and node in cfg.src_file_alias_by_node:
                return str(cfg.src_file_alias_by_node[node])
            if hasattr(cfg, "blame_targets_by_node") and cfg.blame_targets_by_node:
                for bt_set in cfg.blame_targets_by_node.values():
                    for bt in bt_set:
                        if hasattr(bt, "owning_node") and bt.owning_node == node:
                            return str(bt.relative_path if hasattr(bt, "relative_path") else bt)
            if hasattr(cfg, "read_only_files") and cfg.read_only_files:
                for ro in cfg.read_only_files:
                    if hasattr(ro, "owning_node") and ro.owning_node == node:
                        return str(ro.relative_path if hasattr(ro, "relative_path") else ro)
            if hasattr(cfg, "read_write_files") and cfg.read_write_files:
                for rw in cfg.read_write_files:
                    if hasattr(rw, "owning_node") and rw.owning_node == node:
                        return str(rw.relative_path if hasattr(rw, "relative_path") else rw)
    except Exception:
        pass

    addr = str(node.unit_address).strip()
    if ":" in addr:
        pkg, unit_name = addr.split(":", 1)
        pkg = pkg.lstrip("/").strip()
    elif "/" in addr:
        pkg, unit_name = addr.rsplit("/", 1)
        pkg = pkg.lstrip("/").strip()
    else:
        pkg, unit_name = "", addr

    role = str(node.role_address).split(":")[-1].strip().lower() if node.role_address else ""
    role_defs = _get_role_definitions()
    if role in role_defs:
        src_pat = _role_src_pattern(role_defs[role])
        if src_pat:
            formatted = src_pat.replace("{unit_dir}", pkg).replace(
                "{unit_name}", unit_name
            ).strip("/")
            if formatted:
                return formatted

    return f"{pkg}/{unit_name}" if pkg else unit_name


class SessionCoordinator(coordinate.SessionCoordinator):
    """Central session control coordinator facade."""

    tier = agent_session.agent_session

    def __init__(self) -> None:
        self._nodes: List[dag_storage.DagNode] = []
        self._node_states: Dict[
            dag_storage.DagNode, coordinate.TargetState
        ] = {}
        self._alias_to_node: Dict[str, dag_storage.DagNode] = {}
        self._node_to_alias: Dict[dag_storage.DagNode, str] = {}

    def _populate_node_aliases(self, nodes: Sequence[dag_storage.DagNode]) -> None:
        """Registers the supplied nodes as open targets and indexes their aliases."""
        for n in nodes:
            if n not in self._nodes:
                self._nodes.append(n)
            self._node_states[n] = coordinate.TargetState.OPEN

        cfg: Optional[node_config.NodeConfig] = None
        try:
            cfg = get_singleton(node_config.NodeConfig)
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
                and hasattr(cfg, "src_file_alias_by_node")
                and cfg.src_file_alias_by_node
                and n in cfg.src_file_alias_by_node
            ):
                src_alias = cfg.src_file_alias_by_node[n]
            elif cfg is not None and hasattr(cfg, "read_write_files") and cfg.read_write_files:
                for f in cfg.read_write_files:
                    if hasattr(f, "owning_node") and f.owning_node == n:
                        src_alias = str(f.relative_path if hasattr(f, "relative_path") else "")
                        break

            display_alias = src_alias or _node_display_alias(n)
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

    # Contract: Sequence of nodes currently in OPEN state.
    @property
    def open_targets(self) -> Sequence[dag_storage.DagNode]:
        """Sequence of nodes currently in OPEN state."""
        return self._open_nodes()

    def _open_nodes(self) -> List[dag_storage.DagNode]:
        return [
            n
            for n in self._nodes
            if self._node_states.get(n) == coordinate.TargetState.OPEN
        ]

    def _get_target_state(self, node: dag_storage.DagNode) -> coordinate.TargetState:
        return self._node_states.get(node, coordinate.TargetState.OPEN)

    def _set_target_state(
        self, node: dag_storage.DagNode, state: coordinate.TargetState
    ) -> None:
        self._node_states[node] = state

    # Contract: Registers a target node with an alias and initial state in the session.
    def register_node(
        self,
        node: dag_storage.DagNode,
        alias: str,
        state: coordinate.TargetState = coordinate.TargetState.OPEN,
    ) -> None:
        # Explicitly filters out synthetic '//session:target' nodes when registering a node.
        self._nodes = [n for n in self._nodes if n.unit_address != "//session:target"]
        if node not in self._nodes:
            self._nodes.append(node)
        self._node_states[node] = coordinate.TargetState(state)
        normalized = _normalize_alias(alias)
        raw = alias.strip().lstrip("/")
        self._alias_to_node[normalized] = node
        if raw and raw != normalized:
            self._alias_to_node[raw] = node
        self._node_to_alias[node] = normalized

    # Contract: Resolves a DagNode instance from a string alias; falls back to normalized suffix and file proxy matching.
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
        if len(matching) == 1:
            return matching[0]

        # Match by file proxy (e.g. path/to/lib/unit.py or tests/unit_test.py)
        cand_base = os.path.basename(cand)
        cand_stem, _ = os.path.splitext(cand_base)
        cand_unit = cand_stem.removesuffix("_test")
        cand_dir = os.path.dirname(norm_cand)
        parts = cand_dir.split("/") if cand_dir else []
        role_dir = (
            parts.pop()
            if parts and parts[-1] in ("lib", "tests", "low", "high", "planning", "scenarios", "support")
            else None
        )
        cand_pkg = "/".join(parts)

        expected_role: Optional[str] = None
        if cand_stem.endswith("_test") or role_dir == "tests":
            expected_role = "test"
        elif role_dir == "lib":
            expected_role = "lib"
        elif role_dir == "low" or cand_base.endswith(".pyi"):
            expected_role = "low"
        elif role_dir == "high":
            expected_role = "high"
        elif role_dir == "planning":
            expected_role = "planning"
        elif role_dir == "scenarios":
            expected_role = "scenario"

        matching_proxy: List[dag_storage.DagNode] = []
        for node in self._nodes:
            pkg, unit = _extract_unit_info(node)
            node_role = (
                str(node.role_address).split(":")[-1].strip().lower()
                if node.role_address
                else ""
            )
            if expected_role and node_role != expected_role:
                continue
            if cand_unit == unit:
                if not cand_pkg or cand_pkg == pkg or pkg.endswith(cand_pkg) or cand_pkg.endswith(pkg):
                    matching_proxy.append(node)

        if len(matching_proxy) == 1:
            return matching_proxy[0]

        return None

    # Contract: Resolves the primary alias string corresponding to a DagNode.
    def get_alias_for_node(self, node: dag_storage.DagNode) -> str:
        alias = self._node_to_alias.get(node)
        if alias:
            return alias
        return _node_display_alias(node)

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

    # Contract: Resets session node tracking to the supplied nodes.
    def reset_nodes(self, nodes: Sequence[dag_storage.DagNode]) -> None:
        """Resets session node tracking to the supplied nodes."""
        self._node_states.clear()
        self._populate_node_aliases(nodes)

    # Contract: Resolves default target node; selects sole open target, or disambiguates by last_accessed_file or workspace file mtime.
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
            cfg = get_singleton(node_config.NodeConfig)
            rw_files = list(cfg.read_write_files if (cfg and hasattr(cfg, "read_write_files")) else [])
        except (LifecycleResolutionError, KeyError, RuntimeError, ValueError):
            pass

        def _owning_open_node(f: Any) -> Optional[dag_storage.DagNode]:
            owner = f.owning_node if hasattr(f, "owning_node") else None
            if owner is not None:
                return owner if owner in open_set else None
            rel = str(f.relative_path if hasattr(f, "relative_path") else "")
            alias_node = self.get_node_for_alias(rel)
            return alias_node if alias_node in open_set else None

        last_f = last_accessed_file
        if last_f is not None:
            if hasattr(last_f, "relative_path"):
                last_path = str(last_f.relative_path)
            elif hasattr(last_f, "short_name"):
                last_path = str(last_f.short_name)
            else:
                last_path = str(last_f)
            owner = last_f.owning_node if hasattr(last_f, "owning_node") else None
            cand_node = self.get_node_for_alias(last_path) or owner
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

    # Contract: Dispatches work discovery to WorkScheduler, registers discovered nodes as open targets, and updates active session nodes in RoleConfig.
    def dispatch_get_work(
        self,
        subgraph: Optional[subgraph.DagSubgraph] = None,
        dir_scope: Optional[str] = None,
        max_batch_size: Optional[int] = None,
    ) -> work_scheduler.WorkSchedule:
        if max_batch_size is not None and max_batch_size <= 0:
            max_batch_size = None
        scheduler = get_singleton(work_scheduler.WorkScheduler)
        schedule = scheduler.schedule_work(
            subgraph=subgraph, dir_scope=dir_scope, max_batch_size=max_batch_size
        )
        role_cfg = get_singleton(node_config.RoleConfig)

        tasks = list(schedule.tasks)
        storage = get_singleton(dag_storage.DagStorage)

        # Materializes template files for each scheduled task node when missing on disk.
        for task in tasks:
            if hasattr(storage, "materialize_template"):
                storage.materialize_template(task.node)
        self._populate_node_aliases([task.node for task in tasks])
        role_cfg.set_nodes([task.node for task in tasks])
        return work_scheduler.WorkSchedule(tasks=tasks)

    # Contract: Dispatches verification check evaluation for a target or all open targets through VerificationEvaluator.
    def dispatch_check_files(
        self, target_alias: Optional[str] = None
    ) -> verification.VerificationResult:
        evaluator = get_singleton(verification.VerificationEvaluator)
        if target_alias:
            node = self.get_node_for_alias(target_alias)
            if node is None and len(self._open_nodes()) == 1:
                node = self._open_nodes()[0]
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
        return verification.VerificationResult(
            passed=all_passed,
            diagnostic_output=diagnostic,
            is_cached=all_cached,
        )

    # Contract: Dispatches submission gating for target through SubmissionCoordinator and marks target CLEAN on acceptance.
    def dispatch_submit(
        self,
        target_alias: Optional[str] = None,
        change_summary: Optional[str] = None,
        has_modifications: bool = False,
    ) -> coordinate.ControlDispatchOutcome:
        target_node = (
            self.get_node_for_alias(target_alias)
            if target_alias
            else self.resolve_default_target()
        )
        if target_node is None and target_alias and len(self._open_nodes()) == 1:
            target_node = self._open_nodes()[0]
        if (
            target_node is None
            or self._get_target_state(target_node)
            != coordinate.TargetState.OPEN
        ):
            open_list = ", ".join(f"`{self.get_alias_for_node(n)}`" for n in self._open_nodes())
            message = (
                f"Error: Target '{target_alias or ''}' is not an open target. "
                f"Available: {open_list}"
            )
            return coordinate.ControlDispatchOutcome(
                success=False, message=message, remaining_open_targets=self._open_nodes()
            )

        submit_coord = get_singleton(submit.SubmissionCoordinator)
        outcome = submit_coord.submit_target(
            target_node=target_node,
            change_summary=change_summary,
            has_modifications=has_modifications,
            in_batch_dependencies=list(self._in_batch_dependencies(target_node)),
        )
        if outcome.accepted:
            self._set_target_state(target_node, coordinate.TargetState.CLEAN)
        return coordinate.ControlDispatchOutcome(
            success=outcome.accepted,
            message=outcome.message,
            remaining_open_targets=self._open_nodes(),
        )

    # Contract: Dispatches upstream defect attribution via AttributionCoordinator.blame_target, marks source ATTRIBUTED and dependents FAILED.
    def dispatch_blame(
        self,
        source_alias: Optional[str] = None,
        blame_target_alias: Optional[str] = None,
        explanation: str = "",
    ) -> coordinate.ControlDispatchOutcome:
        attrib_coord = get_singleton(attribution.AttributionCoordinator)

        source_node = (
            self.get_node_for_alias(source_alias)
            if source_alias
            else self.resolve_default_target()
        )
        if source_node is None and source_alias and len(self._open_nodes()) == 1:
            source_node = self._open_nodes()[0]
        if source_node is None:
            open_list = ", ".join(f"`{self.get_alias_for_node(n)}`" for n in self._open_nodes())
            return coordinate.ControlDispatchOutcome(
                success=False,
                message=f"Error: No open target found for blame. Available: {open_list}",
                remaining_open_targets=self._open_nodes(),
            )

        blame_target_node = None
        if blame_target_alias:
            try:
                matched_bound = attrib_coord.match_blame_target(
                    source_node, None, blame_target_alias
                )
                if (
                    matched_bound is not None
                    and hasattr(matched_bound, "owning_node")
                    and matched_bound.owning_node is not None
                ):
                    blame_target_node = matched_bound.owning_node
                    self.register_node(
                        blame_target_node,
                        alias=blame_target_alias,
                        state=coordinate.TargetState.ATTRIBUTED,
                    )
            except Exception:
                pass
            if blame_target_node is None:
                cand = self.get_node_for_alias(blame_target_alias)
                if cand is not None and cand != source_node:
                    blame_target_node = cand

        if blame_target_node is None or blame_target_node == source_node:
            return coordinate.ControlDispatchOutcome(
                success=False,
                message=(
                    f"Error: Blame target '{blame_target_alias or ''}' could not be "
                    f"resolved to an upstream dependency."
                ),
                remaining_open_targets=self._open_nodes(),
            )

        outcome = get_singleton(attribution.AttributionCoordinator).blame_target(
            source_node=source_node,
            blame_target_node=blame_target_node,
            explanation=explanation,
            in_batch_dependencies=list(self._in_batch_dependencies(source_node)),
            in_batch_dependents=self._get_in_batch_dependents(source_node),
        )
        if outcome.accepted:
            self._set_target_state(
                source_node, coordinate.TargetState.ATTRIBUTED
            )
            for affected in outcome.affected_nodes:
                if affected != source_node:
                    self._set_target_state(
                        affected, coordinate.TargetState.FAILED
                    )
        return coordinate.ControlDispatchOutcome(
            success=outcome.accepted,
            message=outcome.message,
            remaining_open_targets=self._open_nodes(),
        )

    # Contract: Dispatches failure recording for target via AttributionCoordinator.fail_target and marks affected nodes FAILED.
    def dispatch_fail(
        self,
        target_alias: Optional[str] = None,
        explanation: str = "",
    ) -> coordinate.ControlDispatchOutcome:
        target_node = (
            self.get_node_for_alias(target_alias)
            if target_alias
            else self.resolve_default_target()
        )
        if target_node is None and target_alias and len(self._open_nodes()) == 1:
            target_node = self._open_nodes()[0]
        if target_node is None:
            open_list = ", ".join(f"`{self.get_alias_for_node(n)}`" for n in self._open_nodes())
            return coordinate.ControlDispatchOutcome(
                success=False,
                message=f"Error: No open target found to fail. Available: {open_list}",
                remaining_open_targets=self._open_nodes(),
            )

        outcome = get_singleton(attribution.AttributionCoordinator).fail_target(
            target_node=target_node,
            explanation=explanation,
            in_batch_dependents=self._get_in_batch_dependents(target_node),
        )
        if outcome.accepted:
            for affected in outcome.affected_nodes:
                self._set_target_state(affected, coordinate.TargetState.FAILED)
        return coordinate.ControlDispatchOutcome(
            success=outcome.accepted,
            message=outcome.message,
            remaining_open_targets=self._open_nodes(),
        )
# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T19:49:56Z
# LAST_CHANGED: 2026-10-11T05:03:57Z
# CHANGE: Track node state with the declared target-state values instead of ad-hoc strings, normalize aliases through the alias manager, disambiguate default targets by workspace path modification time, always register scheduled nodes, and prune uncontracted public members
# COVERAGE_AUDIT: 2026-10-15T19:49:56Z
# --- END CLEANROOM METADATA ---


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        SessionCoordinator,
        keys=[SessionCoordinator, coordinate.SessionCoordinator],
        tier=SessionCoordinator.tier,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
