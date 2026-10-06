"""Grounding specification for control_submit."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Protocol, Sequence
from support.lib.grounding_support import AgentSessionTier, InTier
from parts.dag.grounding import dag_storage

__all__ = ["SubmissionOutcome", "SubmissionCoordinator"]


@dataclass(frozen=True)
class SubmissionOutcome:
    accepted: bool
    message: str


class SubmissionCoordinator(InTier[AgentSessionTier], Protocol):
    def submit_target(
        self,
        target_node: dag_storage.DagNode,
        change_summary: Optional[str] = None,
        has_modifications: bool = False,
        in_batch_dependencies: Optional[Sequence[dag_storage.DagNode]] = None,
    ) -> SubmissionOutcome:
        """
        DEFERRED:
        - When verification fails, MUST reject submission.
        - When an in-batch dependency is not clean, MUST reject submission.
        - When auditor role supplies a change summary, MUST reject submission.
        - When files modified and change summary omitted, MUST reject submission.
        - When files unmodified and change summary supplied, MUST reject submission.
        - When accepted, MUST mark target node clean in graph storage and record change message.
        """
        raise NotImplementedError
