from __future__ import annotations
from support.lib.lifecycle import Singleton, SystemTier

from dataclasses import dataclass
from typing import NewType, Optional, Protocol, Set

# Contract: Strong type aliases for unit address, role address, message content, and change description.
UnitAddress = NewType("UnitAddress", str)

RoleAddress = NewType("RoleAddress", str)

MessageContent = NewType("MessageContent", str)

ChangeDescription = NewType("ChangeDescription", str)


# Contract: DagNode identifies a discrete unit of work in the graph.
@dataclass(frozen=True)
class DagNode:
    """Identifies a discrete unit of work in the graph.

    Args:
        unit_address: Unit address identifying the end-artifact being worked on.
        role_address: Role address identifying the phase of work being done to an artifact.
    """

    unit_address: UnitAddress
    role_address: RoleAddress


# Contract: DagDependency defines dependency relationship referring to an upstream node.
@dataclass(frozen=True)
class DagDependency:
    """A dependency relationship referring to an upstream node in the graph.

    Args:
        node: The upstream target node referenced by the dependency.
        is_silent: Indicates whether the dependency is silent to preclude change propagation.
    """

    node: DagNode
    is_silent: bool = False


# Contract: DagMessage sum-type base of the message variants recorded for a node.
@dataclass(frozen=True, init=False)
class DagMessage:
    """Explains why a node requires cleaning.

    Sum-type base of the message variants recorded for a node; it carries no fields of its
    own and therefore generates no constructor.
    """


# Contract: ChangeMessage informs of changes made to upstream dependencies.
@dataclass(frozen=True)
class ChangeMessage(DagMessage):
    """Informs of changes made to upstream dependencies.

    Args:
        content: Text content explaining why the node requires cleaning.
    """

    content: MessageContent = MessageContent("")


# Contract: FeedbackMessage informs of defects detected by downstream dependents blaming a target node.
@dataclass(frozen=True)
class FeedbackMessage(DagMessage):
    """Informs of defects detected by downstream dependents blaming a target node.

    Args:
        content: Text content explaining why the node requires cleaning.
        target: Target dependency node blamed by the feedback message.
    """

    content: MessageContent = MessageContent("")
    target: Optional[DagNode] = None


# Contract: DagStorage stores node graph structure, node status, and messages for dag nodes.
class DagStorage(Singleton[SystemTier], Protocol):
    """Stores node graph structure, node status, and messages for dag nodes.

    INVARIANTS:
    - Direct upstream dependencies of a dag node form a directed acyclic graph.
    """

    # Contract: Provides the set of upstream dependencies for a node.
    def get_dependencies(self, node: DagNode) -> Set[DagDependency]:
        """Provides the set of upstream dependencies for a node.

        Args:
            node: The node whose dependencies are retrieved.

        Returns:
            The set of upstream dependencies for the node.
        """
        ...

    # Contract: Provides the set of messages recorded for a node.
    def get_messages(self, node: DagNode) -> Set[DagMessage]:
        """Provides the set of messages recorded for a node.

        Args:
            node: The node whose messages are retrieved.

        Returns:
            The set of messages explaining why the node requires cleaning.
        """
        ...

    # Contract: Indicates whether a node needs to be cleaned.
    def is_dirty(self, node: DagNode) -> bool:
        """Indicates whether a node needs to be cleaned.

        Args:
            node: The node whose dirty status is checked.

        Returns:
            True if the node needs to be cleaned.

        POSTCONDITIONS:
        - WHEN the declared source file is missing from disk, MUST return true.
        - WHEN in-band metadata is missing or invalid, MUST return true.
        - WHEN in-band metadata is uncleaned with a change description, MUST return true.
        - WHEN in-band metadata contains a dirty tag, MUST return true.
        - WHEN unacted feedback messages exist for the node, MUST return true.
        - WHEN any non-silent dependency was changed after the node was last cleaned, MUST return true.
        """
        ...

    # Contract: Adds a feedback message blaming a dependency target node.
    def add_feedback_message(self, node: DagNode, message: FeedbackMessage) -> None:
        """Adds a feedback message blaming a dependency target node.

        Args:
            node: The dependency target node receiving the feedback message.
            message: The feedback message to record for the node.

        POSTCONDITIONS:
        - MUST record the feedback message in the target node's in-band metadata as unacted feedback.
        """
        ...

    # Contract: Adds a message to a node.
    def add_message(self, message: DagMessage, to: DagNode) -> None:
        """Adds a message to a node.

        Args:
            message: The message to record for the node.
            to: The target node receiving the message.

        POSTCONDITIONS:
        - MUST record the message for the node.
        """
        ...

    # Contract: Marks a node dirty by clearing its clean status and recording a provided reason in in-band metadata.
    def mark_node_dirty(self, node: DagNode, reason: Optional[str] = ...) -> None:
        """Marks a node dirty by clearing its clean status and recording a provided reason in in-band metadata.

        Args:
            node: The node to mark dirty.
            reason: Optional reason explaining why the node is marked dirty.

        POSTCONDITIONS:
        - MUST mark the node dirty so that is_dirty returns true.
        - MUST clear the last cleaned status in the node's in-band metadata.
        - WHEN a dirty reason is provided, MUST record the dirty reason in the node's in-band metadata.
        """
        ...

    # Contract: Marks the target node and all reachable dependencies in its subgraph clean.
    def mark_subgraph_clean(self, node: DagNode) -> None:
        """Marks the target node and all reachable dependencies in its subgraph clean.

        Args:
            node: The root node of the subgraph to mark clean.

        POSTCONDITIONS:
        - MUST mark the target node clean.
        - MUST mark all reachable dependencies of the node clean.
        - MUST materialize missing templates for all nodes in the subgraph.
        """
        ...

    # Contract: Clears all messages from a node.
    def clear_messages(self, node: DagNode) -> None:
        """Clears all messages from a node.

        Args:
            node: The node whose messages are cleared.

        POSTCONDITIONS:
        - MUST clear all messages from the node.
        """
        ...

    # Contract: Marks a node clean in graph storage and on disk.
    def mark_node_clean(
        self, node: DagNode, change_description: Optional[ChangeDescription] = ...
    ) -> None:
        """Marks a node clean in graph storage and on disk.

        Args:
            node: The node being marked clean.
            change_description: Optional summary of modifications made to the node.

        POSTCONDITIONS:
        - WHEN node has a source file and change description is provided, MUST update last changed timestamp, last cleaned timestamp, and change description, and clear unacted feedback and dirty tags.
        - WHEN node has a source file and change description is omitted, MUST update last cleaned timestamp and clear unacted feedback and dirty tags, preserving existing last changed timestamp.
        - WHEN node is an auditor role, MUST stamp audit metadata on all feedback dependencies.
        - MUST clear messages for node.
        - WHEN node has a source file, MUST mark node clean so that node is no longer dirty.
        """
        ...

    # Contract: Materializes initial template content for a node if its source artifact is missing on disk.
    def materialize_template(self, node: DagNode) -> None:
        """Materializes initial template content for a node if its source artifact is missing on disk.

        Args:
            node: The node whose template is materialized.

        POSTCONDITIONS:
        - WHEN node has a declared template and its source artifact does not exist on disk, MUST write formatted template content to disk.
        - WHEN source artifact already exists on disk, MUST preserve existing content without overwriting.
        """
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-11T04:59:20Z
# CHANGE: Align the message sum type with its declaration (base dataclass frozen with init disabled, real default values on the variants) and document every declared operation and postcondition
# --- END CLEANROOM METADATA ---
