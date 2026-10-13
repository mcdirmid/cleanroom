# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-12T23:37:37Z
# LAST_CHANGED: 2026-10-11T05:04:02Z
# CHANGE: Schedule directory-scoped dirty nodes from the role configuration node set when storage exposes no enumeration, and tolerate lifecycle resolution failures in role precedence
# CODE_HASH: d25daba1f784
# COVERAGE_AUDIT: 2026-10-12T23:37:37Z
# QA_AUDIT: 2026-10-12T23:37:36Z
# --- END CLEANROOM METADATA ---

from __future__ import annotations
import os
import tomllib
from typing import Dict, List, Mapping, Optional, Sequence, Set, Tuple
from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleResolutionError,
    Singleton,
    get_default_registry,
    get_singleton,
)
from update_with_ai.parts.agent.lib import agent_config, agent_node_config, agent_session
from update_with_ai.parts.dag.lib import dag_storage, dag_subgraph
from . import control_work_scheduler


def _extract_unit_info(node: dag_storage.DagNode) -> Tuple[str, str]:
    target = node.unit_address
    if ":" in target:
        pkg, unit = target.split(":", 1)
        pkg = pkg.lstrip("/").strip()
        unit = unit.strip()
        return pkg, unit
    return "", target


class WorkScheduler(control_work_scheduler.WorkScheduler, Singleton):
    """Discovers ready tasks across subgraph or directory scope using dynamic role precedence."""

    tier = agent_session.agent_session

    def __init__(self) -> None:
        pass

    def compute_role_precedence(
        self, role_dependencies: Mapping[str, Sequence[str]]
    ) -> Mapping[str, int]:
        """Calculates topological depth rank for roles based on role dependencies."""
        memo: Dict[str, int] = {}
        visiting: Set[str] = set()

        def _clean_name(r: str) -> str:
            return r.split(":")[-1].strip().lower()

        clean_deps: Dict[str, List[str]] = {
            _clean_name(k): [_clean_name(dep) for dep in v]
            for k, v in role_dependencies.items()
        }

        def _get_depth(role: str) -> int:
            if role in memo:
                return memo[role]
            if role in visiting:
                return 0  # Break potential cycles gracefully
            visiting.add(role)
            deps = clean_deps.get(role, [])
            if not deps:
                depth = 0
            else:
                depth = 1 + max(_get_depth(d) for d in deps)
            visiting.remove(role)
            memo[role] = depth
            return depth

        for r in clean_deps:
            _get_depth(r)

        return memo

    def _get_role_precedence_rank(self, role_address: str) -> int:
        """Determines precedence rank for a role address dynamically."""
        clean = role_address.split(":")[-1].strip().lower()
        role_deps: Dict[str, Sequence[str]] = {}
        try:
            cfg = get_singleton(agent_node_config.NodeConfig)
            if cfg is not None:
                for r_name, r_cfg in getattr(cfg, "role_definitions", {}).items():
                    rd = list(getattr(r_cfg, "role_deps", ()))
                    rd += list(getattr(r_cfg, "feedback_role_deps", ()))
                    rd += list(getattr(r_cfg, "silent_role_deps", ()))
                    rd += [s for s in getattr(r_cfg, "star_role_deps", ()) if s.split(":")[-1] != r_name]
                    role_deps[r_name] = rd
        except (LifecycleResolutionError, KeyError, AttributeError, RuntimeError):
            pass
        if not role_deps:
            try:
                for cand in ("cleanroom_roles.toml", "cleanroom_python_roles.toml"):
                    if os.path.isfile(cand):
                        with open(cand, "rb") as f:
                            data = tomllib.load(f)
                            for r_name, r_cfg in data.get("roles", {}).items():
                                rd = list(r_cfg.get("role_deps", ()))
                                rd += list(r_cfg.get("feedback_role_deps", ()))
                                rd += list(r_cfg.get("silent_role_deps", ()))
                                rd += [s for s in r_cfg.get("star_role_deps", ()) if s.split(":")[-1] != r_name]
                                role_deps[r_name] = rd
            except (OSError, tomllib.TOMLDecodeError):
                pass
        if not role_deps:
            return 999
        ranks = self.compute_role_precedence(role_deps)
        return ranks.get(clean, 999)

    def _scan_dir_scope(
        self, storage: dag_storage.DagStorage, dir_scope: str
    ) -> List[dag_storage.DagNode]:
        """Scans the directory scope for dirty nodes whose upstream dependencies are clean."""
        norm_scope = dir_scope.strip().strip("/")
        known_nodes: Set[dag_storage.DagNode] = set(
            getattr(storage, "all_nodes", set()) or set()
        )
        try:
            known_nodes.update(get_singleton(agent_node_config.RoleConfig).nodes)
        except (LifecycleResolutionError, KeyError, RuntimeError, ValueError):
            pass

        candidates: List[dag_storage.DagNode] = []
        for node in sorted(
            known_nodes, key=lambda n: (str(n.unit_address), str(n.role_address))
        ):
            unit_str = str(node.unit_address).strip().strip("/")
            if norm_scope and not unit_str.startswith(norm_scope):
                continue
            if not storage.is_dirty(node):
                continue
            deps_clean = True
            for dep in storage.get_dependencies(node):
                if not dep.is_silent and storage.is_dirty(dep.node):
                    deps_clean = False
                    break
            if deps_clean:
                candidates.append(node)
        return candidates

    def schedule_work(
        self,
        subgraph: Optional[dag_subgraph.DagSubgraph] = None,
        dir_scope: Optional[str] = None,
        max_batch_size: Optional[int] = None,
    ) -> control_work_scheduler.WorkSchedule:
        """Discovers ready tasks across subgraph or directory scope."""
        storage = get_singleton(dag_storage.DagStorage)
        candidate_nodes: List[dag_storage.DagNode] = []

        if subgraph is not None:
            candidate_nodes = list(subgraph.next_ready_batch())
        elif dir_scope is not None:
            candidate_nodes = self._scan_dir_scope(storage, dir_scope)

        # Sort candidate nodes by dynamic role precedence rank, then unit address
        candidate_nodes.sort(
            key=lambda n: (
                self._get_role_precedence_rank(n.role_address),
                n.unit_address,
                n.role_address,
            )
        )

        if max_batch_size is not None and max_batch_size > 0:
            candidate_nodes = candidate_nodes[:max_batch_size]

        tasks: List[control_work_scheduler.ScheduledTask] = []
        for node in candidate_nodes:
            deps = storage.get_dependencies(node)
            dep_paths: List[str] = [
                f"{dep.node.unit_address}:{dep.node.role_address}"
                for dep in deps
            ]

            msgs = storage.get_messages(node)
            feedback_msgs: List[dag_storage.FeedbackMessage] = [
                m for m in msgs if isinstance(m, dag_storage.FeedbackMessage)
            ]

            role_clean = node.role_address.split(":")[-1].strip().lower()
            prompt = f"Implement task for unit '{node.unit_address}' in role '{role_clean}'."
            if feedback_msgs:
                prompt += "\n\n### Open Feedback:\n"
                for fb in feedback_msgs:
                    prompt += f"- {fb.content}\n"

            tasks.append(
                control_work_scheduler.ScheduledTask(
                    node=node,
                    task_prompt=prompt,
                    dependency_paths=dep_paths,
                    feedback_messages=feedback_msgs,
                )
            )

        return control_work_scheduler.WorkSchedule(tasks=tasks)

    def _resolve_grounding_file(
        self,
        node: dag_storage.DagNode,
        source_alias: str,
        n_cfg: agent_node_config.NodeConfig,
    ) -> str:
        pkg, unit_name = _extract_unit_info(node)
        target_stem = os.path.splitext(os.path.basename(source_alias))[0]
        role_clean = node.role_address.split(":")[-1].strip().lower()

        if "logs/" in source_alias or source_alias.endswith(".log"):
            res = (
                source_alias.replace("logs/", "grounding/")
                .replace("_qa.log", ".pyi")
                .replace("_coverage.log", ".pyi")
                .replace(".log", ".pyi")
            )
            if not res.endswith(".pyi"):
                res += ".pyi"
            return res

        if "tests/" in source_alias or source_alias.endswith("_test.py") or source_alias.endswith("_coverage.py"):
            base = source_alias.replace("tests/", "low/")
            for sfx in ("_test.py", "_coverage.py", ".py"):
                if base.endswith(sfx):
                    base = base.removesuffix(sfx)
                    break
            return base + ".pyi"

        is_auditor = bool(
            getattr(n_cfg, "audit_tag", None)
            or not getattr(n_cfg, "source_pattern", None)
            or not source_alias
        )
        if is_auditor:
            for ro in n_cfg.read_only_files:
                ro_path = getattr(ro, "relative_path", str(ro))
                if ro_path.endswith(".pyi") and not ro_path.endswith("guide.pyi"):
                    return ro_path
            return f"low/{unit_name}.pyi"

        if source_alias.endswith(".py"):
            parent_dir = os.path.dirname(source_alias)
            base_parent = os.path.dirname(parent_dir) if parent_dir else ""
            return (
                os.path.join(base_parent, "low", f"{unit_name}.pyi")
                if base_parent
                else f"low/{unit_name}.pyi"
            )

        if source_alias.endswith(".pyi"):
            for ro in n_cfg.read_only_files:
                ro_path = getattr(ro, "relative_path", str(ro))
                if ro_path.endswith(".md") and not ro_path.endswith("guide.md"):
                    ro_stem = os.path.splitext(os.path.basename(ro_path))[0]
                    if ro_stem == target_stem:
                        return ro_path
            if "grounding/" in source_alias:
                return (
                    source_alias.replace("grounding/", "high/").removesuffix(".pyi")
                    + ".md"
                )
            return f"high/{unit_name}.md"

        if "requirements/" in source_alias:
            return source_alias.replace("requirements/", "high/")

        for ro in n_cfg.read_only_files:
            ro_path = getattr(ro, "relative_path", str(ro))
            if (
                ro_path.endswith(".md")
                and not ro_path.endswith("guide.md")
                and ro_path != source_alias
            ):
                return ro_path

        return ""

    def format_task_prompt(self, nodes: Sequence[dag_storage.DagNode]) -> str:
        n_cfg = get_singleton(agent_node_config.NodeConfig)
        storage = get_singleton(dag_storage.DagStorage)

        guide_file_alias: Optional[str] = None
        if n_cfg.guide_file is not None:
            guide_file_alias = n_cfg.guide_file.relative_path
        else:
            for ro in n_cfg.read_only_files:
                if ro.relative_path.endswith(".md"):
                    guide_file_alias = ro.relative_path
                    break

        is_multi_node = len(nodes) > 1

        mapping_lines: List[str] = []
        for n in nodes:
            pkg, unit_name = _extract_unit_info(n)
            default_alias = f"{pkg}/{unit_name}" if pkg else unit_name
            alias_str = n_cfg.src_file_alias_by_node.get(n) or default_alias
            grounding_file = self._resolve_grounding_file(n, alias_str, n_cfg)
            if grounding_file:
                mapping_lines.append(f"{alias_str} with {grounding_file}")
            else:
                mapping_lines.append(alias_str)

        message_lines: List[str] = []
        for n in nodes:
            pkg, unit_name = _extract_unit_info(n)
            default_alias = f"{pkg}/{unit_name}" if pkg else unit_name
            target_name = (
                n_cfg.src_file_alias_by_node.get(n)
                or ", ".join(sorted(f.relative_path for f in n_cfg.read_write_files))
                or default_alias
            )

            def _msg_content(m: dag_storage.DagMessage) -> str:
                if isinstance(
                    m, (dag_storage.ChangeMessage, dag_storage.FeedbackMessage)
                ):
                    return m.content
                return getattr(m, "content", "")

            messages_sorted = sorted(
                storage.get_messages(n),
                key=lambda m: (_msg_content(m), type(m).__name__),
            )
            for msg in messages_sorted:
                msg_content = _msg_content(msg)
                if isinstance(msg, dag_storage.FeedbackMessage):
                    body = f"Fix {target_name} based on feedback: {msg_content}"
                else:
                    msg_kind = (
                        "change"
                        if isinstance(msg, dag_storage.ChangeMessage)
                        else type(msg).__name__.lower().removesuffix("message")
                    )
                    prefix = f"Incoming {msg_kind}"
                    if is_multi_node:
                        body = (
                            f"{prefix} for {target_name}: {msg_content}"
                            if msg_content
                            else f"{prefix} for {target_name}"
                        )
                    else:
                        body = f"{prefix}: {msg_content}" if msg_content else prefix
                message_lines.append(body)

        if n_cfg.is_step_mode:
            parts = []
            parts.append(
                "The following files are supposed to be aligned:\n"
                + "\n".join(mapping_lines)
            )
            if n_cfg.guide and n_cfg.guide.summary:
                parts.append(n_cfg.guide.summary)
            if message_lines:
                parts.append("\n".join(message_lines))
            parts.append("Call advance() when done making edits.")
            return "\n\n".join(p for p in parts if p).strip()

        parts = []
        if guide_file_alias:
            parts.append(
                f"The following files are supposed to be aligned according to guide {guide_file_alias}:\n"
                + "\n".join(mapping_lines)
            )
        else:
            parts.append(
                "The following files are supposed to be aligned:\n"
                + "\n".join(mapping_lines)
            )

        if message_lines:
            parts.append("\n".join(message_lines))

        if guide_file_alias:
            parts.append(f"Read {guide_file_alias} for alignment guidance.")

        if is_multi_node:
            parts.append(
                "When submitting or failing completed units, specify target as <unit_name> (if unique among session units) or <relative_path>/<unit_name> (if ambiguous)."
            )
        else:
            parts.append(
                "When calling submit or fail for a single unit, the target parameter may be omitted."
            )

        return "\n\n".join(p for p in parts if p).strip()


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        WorkScheduler,
        keys=[WorkScheduler, control_work_scheduler.WorkScheduler],
        tier=WorkScheduler.tier,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
