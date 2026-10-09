# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
# LAST_CHANGED: 2026-10-08T00:31:35Z
# CHANGE: Update DagStorage low-level operations: add_feedback_message, mark_node_dirty, mark_subgraph_clean
# CODE_HASH: 373a52388f6c
# LOW_QA_AUDIT: 2026-10-09T21:19:01Z
# --- END CLEANROOM METADATA ---

"""Dag storage low-level interface specification."""

from dataclasses import dataclass
from typing import NewType, Optional, Protocol, Set
from framework import data_type, operation, singleton_type, variant
from support.lib.lifecycle import InTier, SystemTier


UnitAddress = NewType("UnitAddress", str)
RoleAddress = NewType("RoleAddress", str)
MessageContent = NewType("MessageContent", str)
ChangeDescription = NewType("ChangeDescription", str)


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
        - WHEN the declared source file is missing from disk, MUST return true.
        - WHEN in-band metadata is missing or invalid, MUST return true.
        - WHEN in-band metadata is uncleaned with a change description, MUST return true.
        - WHEN in-band metadata contains a dirty tag, MUST return true.
        - WHEN unacted feedback messages exist for the node, MUST return true.
        - WHEN any non-silent dependency was changed after the node was last cleaned, MUST return true.
        """
        ...

    @operation
    def add_feedback_message(self, node: DagNode, message: FeedbackMessage) -> None:
        """Adds a feedback message blaming a dependency target node.

        Args:
            node: The dependency target node receiving the feedback message.
            message: The feedback message to record for the node.

        POSTCONDITIONS:
        - MUST record the feedback message in the target node's in-band metadata as unacted feedback.
        """
        ...

    @operation
    def add_message(self, message: DagMessage, to: DagNode) -> None:
        """Adds a message to a node.

        Args:
            message: The message to record for the node.
            to: The target node receiving the message.

        POSTCONDITIONS:
        - MUST record the message for the node.
        """
        ...

    @operation
    def mark_node_dirty(self, node: DagNode, reason: Optional[str] = ...) -> None:
        """Marks a node dirty by clearing its clean status in in-band metadata.

        Args:
            node: The node to mark dirty.
            reason: Optional reason explaining why the node is marked dirty.

        POSTCONDITIONS:
        - MUST mark the node dirty so that is_dirty returns true.
        - MUST clear the last cleaned status in the node's in-band metadata.
        """
        ...

    @operation
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

    @operation
    def clear_messages(self, node: DagNode) -> None:
        """Clears all messages from a node.

        Args:
            node: The node whose messages are cleared.

        POSTCONDITIONS:
        - MUST clear all messages from the node.
        """
        ...

    @operation
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
        - MUST mark node clean so that node is no longer dirty.
        """
        ...

    @operation
    def materialize_template(self, node: DagNode) -> None:
        """Materializes initial template content for a node if its source artifact is missing on disk.

        Args:
            node: The node whose template is materialized.

        POSTCONDITIONS:
        - WHEN node has a declared template and its source artifact does not exist on disk, MUST write formatted template content to disk.
        - WHEN source artifact already exists on disk, MUST preserve existing content without overwriting.
        """
        ...
