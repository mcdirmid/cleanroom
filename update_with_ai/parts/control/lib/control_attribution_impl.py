# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T00:13:59Z
# LAST_CHANGED: 2026-10-06T11:45:00Z
# CHANGE: add missing imports
# CODE_HASH: 96e0e4d00495
# COVERAGE_AUDIT: 2026-10-07T00:13:59Z
# QA_AUDIT: 2026-10-07T00:13:59Z
# --- END CLEANROOM METADATA ---

from __future__ import annotations
import os
from typing import Any, List, Optional, Sequence
from support.lib.lifecycle import Singleton, get_singleton
from update_with_ai.parts.agent.lib import agent_file_alias, agent_node_config, agent_session
from update_with_ai.parts.dag.lib import dag_storage
from . import control_attribution


class AttributionCoordinator(control_attribution.AttributionCoordinator, Singleton):
    """Coordinates upstream blame attribution, single-paragraph validation, and failure cascades."""

    tier = agent_session.agent_session

    def match_blame_target(
        self, node: dag_storage.DagNode, val: Any, val_str: str
    ) -> Optional[agent_file_alias.BoundFile]:
        """Matches a blame target value against configured blame targets for a node."""
        cfg = get_singleton(agent_node_config.NodeConfig)
        targets = list(cfg.blame_targets_by_node.get(node, set()))
        for bt in targets:
            bt_name = getattr(bt, "relative_path", getattr(bt, "short_name", ""))
            if val is not None and bt == val:
                return bt
            if val_str and bt_name == val_str:
                return bt
        if val_str:
            norm_v = val_str.lstrip("/")
            suffix_matches = [
                bt
                for bt in targets
                if getattr(bt, "relative_path", "").endswith("/" + norm_v)
                or norm_v.endswith("/" + getattr(bt, "relative_path", "").lstrip("/"))
            ]
            if len(suffix_matches) == 1:
                return suffix_matches[0]
            base_matches = [
                bt
                for bt in targets
                if os.path.basename(getattr(bt, "relative_path", ""))
                == os.path.basename(norm_v)
            ]
            if len(base_matches) == 1:
                return base_matches[0]
        return None

    def blame_target(
        self,
        source_node: dag_storage.DagNode,
        blame_target_node: dag_storage.DagNode,
        explanation: str,
        in_batch_dependencies: Optional[Sequence[dag_storage.DagNode]] = None,
        in_batch_dependents: Optional[Sequence[dag_storage.DagNode]] = None,
    ) -> control_attribution.AttributionOutcome:
        """Attributes defect to an upstream dependency node."""
        storage = get_singleton(dag_storage.DagStorage)

        # 1. Single-paragraph critique validation
        if "\n" in explanation or "\r" in explanation:
            return control_attribution.AttributionOutcome(
                accepted=False,
                message="Error: Blame explanation must be a single paragraph without newlines.",
                affected_nodes=[],
            )

        # 2. Upstream dependency validation
        deps = storage.get_dependencies(source_node)
        upstream_nodes = {dep.node for dep in deps}
        if blame_target_node not in upstream_nodes:
            allowed = ", ".join(f"`{n.unit_address}:{n.role_address}`" for n in upstream_nodes)
            return control_attribution.AttributionOutcome(
                accepted=False,
                message=f"Error: Target '{blame_target_node.unit_address}:{blame_target_node.role_address}' is not an upstream dependency. Available: {allowed}",
                affected_nodes=[],
            )

        # 3. In-batch dependencies must be clean
        if in_batch_dependencies:
            for dep in in_batch_dependencies:
                if storage.is_dirty(dep):
                    return control_attribution.AttributionOutcome(
                        accepted=False,
                        message=f"Error: In-batch dependency '{dep.unit_address}:{dep.role_address}' must be submitted before dependent targets.",
                        affected_nodes=[],
                    )

        # 4. Inject feedback into culprit node (which marks culprit dirty per contract)
        feedback = dag_storage.FeedbackMessage(
            content=dag_storage.MessageContent(explanation.strip()),
            target=blame_target_node,
        )
        storage.add_message(feedback, to=blame_target_node)

        # 5. Mark source and fail in-batch dependents
        affected: List[dag_storage.DagNode] = [source_node]
        if in_batch_dependents:
            for dep in in_batch_dependents:
                affected.append(dep)

        return control_attribution.AttributionOutcome(
            accepted=True,
            message=f"Defect attributed to upstream dependency '{blame_target_node.unit_address}:{blame_target_node.role_address}'.",
            affected_nodes=affected,
        )

    def fail_target(
        self,
        target_node: dag_storage.DagNode,
        explanation: str,
        in_batch_dependents: Optional[Sequence[dag_storage.DagNode]] = None,
    ) -> control_attribution.AttributionOutcome:
        """Records task failure and preserves dirty state on target node."""
        affected: List[dag_storage.DagNode] = [target_node]
        if in_batch_dependents:
            for dep in in_batch_dependents:
                affected.append(dep)

        return control_attribution.AttributionOutcome(
            accepted=True,
            message=f"Target '{target_node.unit_address}:{target_node.role_address}' failed: {explanation.strip()}",
            affected_nodes=affected,
        )
