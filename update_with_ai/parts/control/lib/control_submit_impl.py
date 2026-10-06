# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-06T10:45:00Z
# LAST_CHANGED: 2026-10-06T11:45:00Z
# CHANGE: handle get_messages defensively for mock storage
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from typing import Optional, Sequence
from support.lib.lifecycle import Singleton, get_singleton
from update_with_ai.parts.agent.lib import agent_node_config, agent_session
from update_with_ai.parts.dag.lib import dag_storage
from . import control_submit, control_verification


def _is_auditor_node(node: dag_storage.DagNode) -> bool:
    """Checks whether the node's role is classified as an auditor."""
    cfg = get_singleton(agent_node_config.NodeConfig)
    role_clean = node.role_address.split(":")[-1].strip().lower()
    role_cfg = getattr(cfg, "role_definitions", {}).get(role_clean)
    if role_cfg is not None and getattr(role_cfg, "is_auditor", False):
        return True
    return role_clean in ("grounding_qa", "qa", "coverage")


class SubmissionCoordinator(control_submit.SubmissionCoordinator, Singleton):
    """Coordinates submission gating, change summary rules, and graph status mutation."""

    tier = agent_session.agent_session

    def __init__(self) -> None:
        pass

    def submit_target(
        self,
        target_node: dag_storage.DagNode,
        change_summary: Optional[str] = None,
        has_modifications: bool = False,
        in_batch_dependencies: Optional[Sequence[dag_storage.DagNode]] = None,
    ) -> control_submit.SubmissionOutcome:
        """Validates submission gating rules and marks target clean in graph storage."""
        # 1. Verification precondition check
        verif = get_singleton(control_verification.VerificationEvaluator)
        verif_res = verif.evaluate_verification(target_node)
        if not verif_res.passed:
            return control_submit.SubmissionOutcome(
                accepted=False,
                message=f"Verification is failing. Diagnostic output:\n{verif_res.diagnostic_output}",
            )

        # 2. In-batch dependencies must be clean
        storage = get_singleton(dag_storage.DagStorage)
        if in_batch_dependencies:
            for dep in in_batch_dependencies:
                if storage.is_dirty(dep):
                    return control_submit.SubmissionOutcome(
                        accepted=False,
                        message=f"Error: In-batch dependency '{dep.unit_address}:{dep.role_address}' must be submitted before dependent targets.",
                    )

        # 3. Initial implementation and feedback checks
        node_msgs = (
            storage.get_messages(target_node)
            if hasattr(storage, "get_messages")
            else []
        )
        is_initial_implement = any(
            isinstance(m, dag_storage.ChangeMessage)
            and str(m.content).strip().lower().startswith("implement ")
            for m in node_msgs
        )
        if is_initial_implement and not has_modifications:
            return control_submit.SubmissionOutcome(
                accepted=False,
                message="Error: Initial implementation task requires workspace file modifications before submitting.",
            )

        cfg = get_singleton(agent_node_config.NodeConfig)
        if getattr(cfg, "feedback", None) and not has_modifications:
            return control_submit.SubmissionOutcome(
                accepted=False,
                message="Error: Session feedback is present but no workspace files were modified.",
            )

        # 4. Auditor role check
        is_auditor = _is_auditor_node(target_node)
        summary_str = str(change_summary or "").strip()

        if is_auditor and summary_str:
            return control_submit.SubmissionOutcome(
                accepted=False,
                message="Error: Change summaries are not permitted for audit nodes.",
            )

        # 4. Change summary rules for non-auditors
        if not is_auditor:
            if has_modifications and not summary_str:
                return control_submit.SubmissionOutcome(
                    accepted=False,
                    message="Error: Workspace files were modified but change_summary was not provided.",
                )
            if not has_modifications and summary_str:
                return control_submit.SubmissionOutcome(
                    accepted=False,
                    message="Error: Change summaries are not permitted when submitting without workspace file modifications.",
                )

        # 5. Commit clean state and record change message
        change_desc = dag_storage.ChangeDescription(summary_str) if summary_str else None
        storage.mark_node_clean(target_node, change_desc)
        if summary_str:
            storage.add_message(
                dag_storage.ChangeMessage(content=dag_storage.MessageContent(summary_str)),
                to=target_node,
            )

        return control_submit.SubmissionOutcome(
            accepted=True,
            message=f"Target '{target_node.unit_address}:{target_node.role_address}' submitted successfully.",
        )
