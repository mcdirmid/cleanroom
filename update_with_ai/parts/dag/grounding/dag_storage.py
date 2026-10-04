"""Dag storage grounding specification."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping, NewType, Optional, Protocol, Sequence, Set
from support.lib.grounding_support import InTier, SystemTier, only_elem


UnitAddress = NewType("UnitAddress", str)
RoleAddress = NewType("RoleAddress", str)
MessageContent = NewType("MessageContent", str)


@dataclass(frozen=True)
class DagNode:
    unit_address: UnitAddress
    role_address: RoleAddress


@dataclass(frozen=True)
class DagDependency:
    node: DagNode
    is_silent: bool = False


@dataclass(frozen=True, init=False)
class DagMessage:
    pass


@dataclass(frozen=True)
class ChangeMessage(DagMessage):
    content: MessageContent = MessageContent("")


@dataclass(frozen=True)
class FeedbackMessage(DagMessage):
    content: MessageContent = MessageContent("")
    target: Optional[DagNode] = None


class DagStorage(InTier[SystemTier], Protocol):
    """
    INVARIANTS:
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
        - WHEN the declared source file is missing from disk, MUST return true.
        - WHEN in-band metadata is missing or invalid, MUST return true.
        - WHEN in-band metadata is uncleaned with a change description, MUST return true.
        - WHEN unacted feedback messages exist for the node, MUST return true.
        - WHEN any non-silent dependency was changed after the node was last cleaned, MUST return true.
        """
        _node: DagNode = node
        raise NotImplementedError

    def add_message(self, message: DagMessage, to: DagNode) -> None:
        """
        DEFERRED:
        - MUST add the message to the node.
        - WHEN a change message is added, MUST mark the node dirty by clearing its last cleaned status.
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
