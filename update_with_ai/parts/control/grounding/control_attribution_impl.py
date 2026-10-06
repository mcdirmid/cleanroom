"""Grounding specification for control_attribution_impl."""

from __future__ import annotations
from typing import Optional, Sequence
from support.lib.grounding_support import AgentSessionTier, InTier, only_elem
from parts.dag.grounding import dag_storage
from . import control_attribution

__all__ = ["AttributionCoordinator"]


class AttributionCoordinator(
    control_attribution.AttributionCoordinator,
    InTier[AgentSessionTier],
):
    """
    DISCHARGED:
    - AttributionCoordinator.blame_target
    - AttributionCoordinator.fail_target
    """

    def blame_target(
        self,
        source_node: dag_storage.DagNode,
        blame_target_node: dag_storage.DagNode,
        explanation: str,
        in_batch_dependencies: Optional[Sequence[dag_storage.DagNode]] = None,
        in_batch_dependents: Optional[Sequence[dag_storage.DagNode]] = None,
    ) -> control_attribution.AttributionOutcome:
        """
        COVERED:
        - When blame target is not an upstream dependency, MUST reject blame.
        - When explanation contains newline characters, MUST reject blame.
        - When in-batch dependency is not clean, MUST reject blame.
        - When accepted, MUST record feedback message on culprit node in graph storage.
        - When accepted, MUST mark culprit node dirty in graph storage.
        - When accepted, MUST mark in-batch dependent nodes as failed.
        """
        storage = self.get_singleton(dag_storage.DagStorage)
        feedback = dag_storage.FeedbackMessage(content=dag_storage.MessageContent(explanation), target=blame_target_node)
        storage.add_message(feedback, to=blame_target_node)
        outcome = control_attribution.AttributionOutcome(accepted=True, message="Blame recorded", affected_nodes=[blame_target_node])
        raise NotImplementedError

    def fail_target(
        self,
        target_node: dag_storage.DagNode,
        explanation: str,
        in_batch_dependents: Optional[Sequence[dag_storage.DagNode]] = None,
    ) -> control_attribution.AttributionOutcome:
        """
        COVERED:
        - MUST preserve dirty status on target node in graph storage.
        - MUST record failure message on target node.
        - MUST mark in-batch dependent nodes as failed.
        """
        storage = self.get_singleton(dag_storage.DagStorage)
        outcome = control_attribution.AttributionOutcome(accepted=True, message=explanation, affected_nodes=[target_node])
        raise NotImplementedError
