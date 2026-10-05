# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T20:52:01Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 033e2d7c19fc
# GROUNDING_QA_AUDIT: 2026-10-05T20:52:01Z
# --- END CLEANROOM METADATA ---

"""Dag storage grounding specification."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping, NewType, Optional, Protocol, Sequence, Set
from support.lib.grounding_support import InTier, SystemTier, only_elem


UnitAddress = NewType("UnitAddress", str)
RoleAddress = NewType("RoleAddress", str)
MessageContent = NewType("MessageContent", str)
ChangeDescription = NewType("ChangeDescription", str)


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

    def mark_node_clean(
        self, node: DagNode, change_description: Optional[ChangeDescription] = None
    ) -> None:
        """
        DEFERRED:
        - WHEN node has a source file and change description is provided, MUST update last changed timestamp, last cleaned timestamp, and change description, and clear unacted feedback.
        - WHEN node has a source file and change description is omitted, MUST update last cleaned timestamp and clear unacted feedback, preserving existing last changed timestamp.
        - WHEN node is an auditor role, MUST stamp audit metadata on all feedback dependencies.
        - MUST clear messages for node.
        - MUST mark node clean so that node is no longer dirty.
        - Deferred to refining subtype in bazel_storage_impl.py.
        """
        raise NotImplementedError

    def materialize_template(self, node: DagNode) -> None:
        """
        DEFERRED:
        - WHEN node has a declared template and its source artifact does not exist on disk, MUST write formatted template content to disk.
        - WHEN source artifact already exists on disk, MUST preserve existing content without overwriting.
        - Deferred to refining subtype in bazel_storage_impl.py.
        """
        raise NotImplementedError
