"""Dag storage low-level interface specification."""

from dataclasses import dataclass
from typing import NewType, Optional, Protocol, Set
from framework import data_type, operation, singleton_type, variant
from support.lib.lifecycle import InTier, SystemTier


UnitAddress = NewType("UnitAddress", str)
RoleAddress = NewType("RoleAddress", str)
MessageContent = NewType("MessageContent", str)


@dataclass(frozen=True)
@data_type
class DagNode:
    """Identifies a discrete unit of work in the graph.

    Args:
        unit_address: Unit address identifying the end-artifact being worked on.
        role_address: Role address identifying the phase of work being done to an artifact.
    """
    unit_address: UnitAddress
    role_address: RoleAddress


@dataclass(frozen=True)
@data_type
class DagDependency:
    """A dependency relationship referring to an upstream node in the graph.

    Args:
        node: The upstream target node referenced by the dependency.
        is_silent: Indicates whether the dependency is silent to preclude change propagation.
    """
    node: DagNode
    is_silent: bool = ...


@dataclass(frozen=True, init=False)
@data_type
class DagMessage:
    """Explains why a node requires cleaning."""
    ...


@dataclass(frozen=True)
@variant
class ChangeMessage(DagMessage):
    """Informs of changes made to upstream dependencies.

    Args:
        content: Text content explaining why the node requires cleaning.
    """
    content: MessageContent = ...


@dataclass(frozen=True)
@variant
class FeedbackMessage(DagMessage):
    """Informs of defects detected by downstream dependents blaming a target node.

    Args:
        content: Text content explaining why the node requires cleaning.
        target: Target dependency node blamed by the feedback message.
    """
    content: MessageContent = ...
    target: Optional[DagNode] = ...


@singleton_type("system")
class DagStorage(InTier[SystemTier], Protocol):
    """Stores graph structure, node status, and message propagation across nodes.

    INVARIANTS:
    - Direct upstream dependencies of a dag node form a directed acyclic graph.
    """

    @operation
    def get_dependencies(self, node: DagNode) -> Set[DagDependency]:
        """Provides the set of upstream dependencies for a node.

        Args:
            node: The node whose dependencies are retrieved.

        Returns:
            The set of upstream dependencies for the node.

        POSTCONDITIONS:
        - MUST return the set of upstream dependencies for the node.
        """
        ...

    @operation
    def get_dependents(self, node: DagNode) -> Set[DagNode]:
        """Provides the set of downstream nodes depending on a node.

        Args:
            node: The node whose dependents are retrieved.

        Returns:
            The set of downstream nodes depending on the node.

        POSTCONDITIONS:
        - MUST return the set of downstream nodes depending on the node.
        """
        ...

    @operation
    def get_messages(self, node: DagNode) -> Set[DagMessage]:
        """Provides the set of messages recorded for a node.

        Args:
            node: The node whose messages are retrieved.

        Returns:
            The set of messages explaining why the node requires cleaning.

        POSTCONDITIONS:
        - MUST return the set of messages recorded for the node.
        """
        ...

    @operation
    def is_dirty(self, node: DagNode) -> bool:
        """Indicates whether a node needs to be cleaned.

        Args:
            node: The node whose dirty status is checked.

        Returns:
            True if the node needs to be cleaned.

        POSTCONDITIONS:
        - MUST return whether the node needs to be cleaned.
        - WHEN the node has messages, MUST return true.
        """
        ...

    @operation
    def register_dependent(self, node: DagNode) -> None:
        """Registers a node as a dependent to all of its non-silent dependencies.

        Args:
            node: The node to register as a dependent.

        POSTCONDITIONS:
        - MUST register the node as a dependent across its non-silent dependencies.
        - MUST exclude silent dependencies when registering the node as a dependent.
        """
        ...

    @operation
    def clear_dependents(self, node: DagNode) -> None:
        """Clears all recorded dependents of a node.

        Args:
            node: The node whose recorded dependents are emptied.

        POSTCONDITIONS:
        - MUST clear all registered dependents from the node.
        """
        ...

    @operation
    def add_message(self, message: DagMessage, to: DagNode) -> None:
        """Adds a message to a node explaining why it needs cleaning.

        Args:
            message: The message to record for the node.
            to: The target node receiving the message.

        POSTCONDITIONS:
        - MUST add the message to the node.
        """
        ...

    @operation
    def clear_messages(self, node: DagNode) -> None:
        """Clears all messages from a node.

        Args:
            node: The node whose messages are cleared.

        POSTCONDITIONS:
        - MUST clear all messages from the node.
        """
        ...
