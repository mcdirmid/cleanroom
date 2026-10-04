"""Dag storage grounding specification module."""

from __future__ import annotations
from dataclasses import dataclass
from typing import NewType, Optional, Protocol, Set
from support.lib.grounding_support import InTier, SystemTier, only_elem

UnitAddress = NewType("UnitAddress", str)
RoleAddress = NewType("RoleAddress", str)
MessageContent = NewType("MessageContent", str)


@dataclass(frozen=True)
class DagNode:
    """Identifies a discrete unit of work in the graph."""
    unit_address: UnitAddress
    role_address: RoleAddress


@dataclass(frozen=True)
class DagDependency:
    """A dependency relationship referring to an upstream node in the graph."""
    node: DagNode
    is_silent: bool = False


@dataclass(frozen=True)
class DagMessage:
    """Explains why a node requires cleaning."""
    pass


@dataclass(frozen=True)
class ChangeMessage(DagMessage):
    """Informs of changes made to upstream dependencies."""
    content: MessageContent = MessageContent("")


@dataclass(frozen=True)
class FeedbackMessage(DagMessage):
    """Informs of defects detected by downstream dependents blaming a target node."""
    content: MessageContent = MessageContent("")
    target: Optional[DagNode] = None


class DagStorage(InTier[SystemTier], Protocol):
    """Stores graph structure, node status, and message propagation across nodes.

    DEFERRED:
    - Direct upstream dependencies of a dag node form a directed acyclic graph.
    """

    def get_dependencies(self, node: DagNode) -> Set[DagDependency]:
        """
        DEFERRED:
        - MUST return the set of upstream dependencies for the node.
        - Deferred to refining subtype in bazel_storage_impl.py.
        """
        raise NotImplementedError

    def get_dependents(self, node: DagNode) -> Set[DagNode]:
        """
        DEFERRED:
        - MUST return the set of downstream nodes depending on the node.
        - Deferred to refining subtype in bazel_storage_impl.py.
        """
        raise NotImplementedError

    def get_messages(self, node: DagNode) -> Set[DagMessage]:
        """
        DEFERRED:
        - MUST return the set of messages recorded for the node.
        - Deferred to refining subtype in bazel_storage_impl.py.
        """
        raise NotImplementedError

    def is_dirty(self, node: DagNode) -> bool:
        """
        COVERED:
        - MUST return whether the node needs to be cleaned.
          - Condition knowledge: test whether node requires cleaning based on messages.
          - Consequent knowledge: return boolean indicator.
        - WHEN the node has messages, MUST return true.
          - Condition knowledge: test whether messages set is non-empty.
          - Consequent knowledge: return True.        """
        messages: Set[DagMessage] = self.get_messages(node)
        _has_messages: bool = len(messages) > 0
        raise NotImplementedError

    def register_dependent(self, node: DagNode) -> None:
        """
        COVERED:
        - MUST exclude silent dependencies when registering the node as a dependent.
          - Condition knowledge: inspect dep.is_silent.
          - Consequent knowledge: omit from dependent registration.

        DEFERRED:
        - MUST register the node as a dependent across its non-silent dependencies.
        - Deferred to refining subtype in bazel_storage_impl.py.
        """
        deps: Set[DagDependency] = self.get_dependencies(node)
        sample_dep: DagDependency = only_elem(deps)
        _is_silent: bool = sample_dep.is_silent
        _upstream_node: DagNode = sample_dep.node
        raise NotImplementedError

    def clear_dependents(self, node: DagNode) -> None:
        """
        DEFERRED:
        - MUST clear all registered dependents from the node.
        - Deferred to refining subtype in bazel_storage_impl.py.
        """
        raise NotImplementedError

    def add_message(self, message: DagMessage, to: DagNode) -> None:
        """
        DEFERRED:
        - MUST add the message to the node.
        - Deferred to refining subtype in bazel_storage_impl.py.
        """
        raise NotImplementedError

    def clear_messages(self, node: DagNode) -> None:
        """
        DEFERRED:
        - MUST clear all messages from the node.
        - Deferred to refining subtype in bazel_storage_impl.py.
        """
        raise NotImplementedError
