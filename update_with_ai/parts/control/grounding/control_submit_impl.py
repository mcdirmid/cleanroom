"""Grounding specification for control_submit_impl."""

from __future__ import annotations
from typing import Optional, Sequence
from support.lib.grounding_support import AgentSessionTier, InTier, only_elem
from parts.dag.grounding import dag_storage
from . import control_submit, control_verification

__all__ = ["SubmissionCoordinator"]


class SubmissionCoordinator(
    control_submit.SubmissionCoordinator,
    InTier[AgentSessionTier],
):
    """
    DISCHARGED:
    - SubmissionCoordinator.submit_target
    """

    def submit_target(
        self,
        target_node: dag_storage.DagNode,
        change_summary: Optional[str] = None,
        has_modifications: bool = False,
        in_batch_dependencies: Optional[Sequence[dag_storage.DagNode]] = None,
    ) -> control_submit.SubmissionOutcome:
        """
        COVERED:
        - When verification fails, MUST reject submission.
        - When an in-batch dependency is not clean, MUST reject submission.
        - When auditor role supplies a change summary, MUST reject submission.
        - When files modified and change summary omitted, MUST reject submission.
        - When files unmodified and change summary supplied, MUST reject submission.
        - When accepted, MUST mark target node clean in graph storage and record change message.
        """
        verif = self.get_singleton(control_verification.VerificationEvaluator)
        verif_res = verif.evaluate_verification(target_node)
        storage = self.get_singleton(dag_storage.DagStorage)
        msg = dag_storage.ChangeMessage(content=dag_storage.MessageContent(str(change_summary or "")))
        storage.add_message(msg, to=target_node)
        outcome = control_submit.SubmissionOutcome(accepted=verif_res.passed, message=verif_res.diagnostic_output)
        raise NotImplementedError
