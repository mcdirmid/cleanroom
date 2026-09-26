from dataclasses import dataclass
from typing import Optional, Protocol, Set
from framework import data_type, operation, singleton_type, variant
from support.lib.lifecycle import InTier, SystemTier


@dataclass(frozen=True)
@data_type
class DagNode:
    """Identifies a discrete unit of work in the graph.

    Args:
        unit_address: Unit address identifying the end-artifact being worked on.
        role_address: Role address identifying the phase of work being done to an artifact.
    """
    unit_address: str
    role_address: str


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
    content: str = ...


@dataclass(frozen=True)
@variant
class FeedbackMessage(DagMessage):
    """Informs of defects detected by downstream dependents blaming a target node.

    Args:
        content: Text content explaining why the node requires cleaning.
        target: Target dependency node blamed by the feedback message.
    """
    content: str = ...
    target: Optional[DagNode] = ...


@singleton_type("system")
class DagStorage(InTier[SystemTier], Protocol):
    """Stores graph structure, node status, and message propagation across nodes."""

    @operation
    def get_dependencies(self, node: DagNode) -> Set[DagDependency]:
        """Provides the set of upstream dependencies for a node.

        Args:
            node: The node whose dependencies are retrieved.

        Returns:
            The set of upstream dependencies for the node.

        GROUNDING_PROVISIONS:
        - knows("upstream_dependencies", Set[DagDependency]): Exposes upstream dependencies for a node to satisfy requirement 5.
        """
        ...

    @operation
    def get_dependents(self, node: DagNode) -> Set[DagNode]:
        """Provides the set of downstream nodes depending on a node.

        Args:
            node: The node whose dependents are retrieved.

        Returns:
            The set of downstream nodes depending on the node.

        GROUNDING_PROVISIONS:
        - knows("downstream_dependents", Set[DagNode]): Exposes downstream dependents for a node to satisfy requirement 7.
        """
        ...

    @operation
    def get_messages(self, node: DagNode) -> Set[DagMessage]:
        """Provides the set of messages recorded for a node.

        Args:
            node: The node whose messages are retrieved.

        Returns:
            The set of messages explaining why the node requires cleaning.

        GROUNDING_PROVISIONS:
        - knows("cleaning_messages", Set[DagMessage]): Exposes recorded cleaning messages for a node to satisfy requirement 11.
        """
        ...

    @operation
    def is_dirty(self, node: DagNode) -> bool:
        """Indicates whether a node needs to be cleaned.

        Args:
            node: The node whose dirty status is checked.

        Returns:
            True if the node has messages requiring cleaning, False otherwise.

        REQUIREMENTS:
        - WHEN node has messages, MUST return True.

        GROUNDING_PROVISIONS:
        - knows("cleaning_required", bool): Evaluates whether a node requires cleaning to satisfy requirement 13.
        """
        ...

    @operation
    def register_dependent(self, node: DagNode) -> None:
        """Registers a node as a dependent to all of its non-silent dependencies.

        Args:
            node: The node to register as a dependent.

        REQUIREMENTS:
        - MUST add the node to the dependents of all of its non-silent dependencies.

        GROUNDING_PROVISIONS:
        - action("register_dependent", DagNode): Registers a node as a dependent of non-silent dependencies to satisfy requirement 6.
        """
        ...

    @operation
    def clear_dependents(self, node: DagNode) -> None:
        """Clears all recorded dependents of a node.

        Args:
            node: The node whose recorded dependents are emptied.

        REQUIREMENTS:
        - MUST empty all recorded dependents for that node.

        GROUNDING_PROVISIONS:
        - action("clear_dependents", DagNode): Clears recorded dependents for a node to satisfy requirement 8.
        """
        ...

    @operation
    def add_message(self, message: DagMessage, to: DagNode) -> None:
        """Adds a message to a node explaining why it needs cleaning.

        Args:
            message: The message to record for the node.
            to: The target node receiving the message.

        REQUIREMENTS:
        - MUST record the message for the target node.

        GROUNDING_PROVISIONS:
        - action("add_message", DagMessage): Adds a cleaning message to a node to satisfy requirement 10.
        """
        ...

    @operation
    def clear_messages(self, node: DagNode) -> None:
        """Clears all messages from a node.

        Args:
            node: The node whose messages are cleared.

        REQUIREMENTS:
        - MUST remove all recorded messages for that node.

        GROUNDING_PROVISIONS:
        - action("clear_messages", DagNode): Clears recorded messages for a node to satisfy requirement 12.
        """
        ...

