# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
# LAST_CHANGED: 2026-10-09T18:34:37Z
# CHANGE: Fix dataclass field defaults in DagDependency, ChangeMessage, and FeedbackMessage
# CODE_HASH: 8b4133fa1611
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from typing import NewType, Optional, Protocol, Set
from dataclasses import dataclass

# Requirements specified in dag_storage.pyi

UnitAddress = NewType('UnitAddress', str)

RoleAddress = NewType('RoleAddress', str)

MessageContent = NewType('MessageContent', str)

ChangeDescription = NewType('ChangeDescription', str)

@dataclass(frozen=True)
class DagNode:
    # TODO_DagNode_body
    unit_address: UnitAddress
    role_address: RoleAddress


@dataclass(frozen=True)
class DagDependency:
    # TODO_DagDependency_body
    node: DagNode
    is_silent: bool = False


@dataclass(frozen=True)
class DagMessage:
    # TODO_DagMessage_body
    pass


@dataclass(frozen=True)
class ChangeMessage(DagMessage):
    # TODO_ChangeMessage_body
    content: MessageContent = MessageContent("")


@dataclass(frozen=True)
class FeedbackMessage(DagMessage):
    # TODO_FeedbackMessage_body
    content: MessageContent = MessageContent("")
    target: Optional[DagNode] = None


class DagStorage(Protocol):
    def get_dependencies(self, node: DagNode) -> Set[DagDependency]:
        # TODO_get_dependencies_body
        ...

    def get_messages(self, node: DagNode) -> Set[DagMessage]:
        # TODO_get_messages_body
        ...

    def is_dirty(self, node: DagNode) -> bool:
        # TODO_is_dirty_body
        ...

    def add_feedback_message(self, node: DagNode, message: FeedbackMessage) -> None:
        # TODO_add_feedback_message_body
        ...

    def add_message(self, message: DagMessage, to: DagNode) -> None:
        # TODO_add_message_body
        ...

    def mark_node_dirty(self, node: DagNode, reason: Optional[str]=...) -> None:
        # TODO_mark_node_dirty_body
        ...

    def mark_subgraph_clean(self, node: DagNode) -> None:
        # TODO_mark_subgraph_clean_body
        ...

    def clear_messages(self, node: DagNode) -> None:
        # TODO_clear_messages_body
        ...

    def mark_node_clean(self, node: DagNode, change_description: Optional[ChangeDescription]=...) -> None:
        # TODO_mark_node_clean_body
        ...

    def materialize_template(self, node: DagNode) -> None:
        # TODO_materialize_template_body
        ...
