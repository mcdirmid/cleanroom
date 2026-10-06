"""Grounding specification for control_attribution."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Protocol, Sequence
from support.lib.grounding_support import AgentSessionTier, InTier
from parts.dag.grounding import dag_storage

__all__ = ["AttributionOutcome", "AttributionCoordinator"]


@dataclass(frozen=True)
class AttributionOutcome:
    accepted: bool
    message: str
    affected_nodes: Sequence[dag_storage.DagNode]


class AttributionCoordinator(InTier[AgentSessionTier], Protocol):
    def blame_target(
        self,
        source_node: dag_storage.DagNode,
        blame_target_node: dag_storage.DagNode,
        explanation: str,
        in_batch_dependencies: Optional[Sequence[dag_storage.DagNode]] = None,
        in_batch_dependents: Optional[Sequence[dag_storage.DagNode]] = None,
    ) -> AttributionOutcome:
        """
        DEFERRED:
        - When blame target is not an upstream dependency, MUST reject blame.
        - When explanation contains newline characters, MUST reject blame.
        - When in-batch dependency is not clean, MUST reject blame.
        - When accepted, MUST record feedback message on culprit node in graph storage.
        - When accepted, MUST mark culprit node dirty in graph storage.
        - When accepted, MUST mark in-batch dependent nodes as failed.
        """
        raise NotImplementedError

    def fail_target(
        self,
        target_node: dag_storage.DagNode,
        explanation: str,
        in_batch_dependents: Optional[Sequence[dag_storage.DagNode]] = None,
    ) -> AttributionOutcome:
        """
        DEFERRED:
        - MUST preserve dirty status on target node in graph storage.
        - MUST record failure message on target node.
        - MUST mark in-batch dependent nodes as failed.
        """
        raise NotImplementedError
