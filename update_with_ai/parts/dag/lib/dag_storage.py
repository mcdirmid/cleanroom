# Requirements specified in dag_storage.pyi
from dataclasses import dataclass
from typing import NewType, Optional, Protocol, Set

UnitAddress = NewType("UnitAddress", str)
RoleAddress = NewType("RoleAddress", str)
MessageContent = NewType("MessageContent", str)
ChangeDescription = NewType("ChangeDescription", str)


@dataclass(frozen=True)
class DagNode:
    unit_address: UnitAddress
    role_address: RoleAddress = RoleAddress("")


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


class DagStorage(Protocol):
    def get_dependencies(self, node: DagNode) -> Set[DagDependency]: ...

    def get_messages(self, node: DagNode) -> Set[DagMessage]: ...

    def is_dirty(self, node: DagNode) -> bool: ...

    def add_message(self, message: DagMessage, to: DagNode) -> None: ...

    def clear_messages(self, node: DagNode) -> None: ...
    def mark_node_clean(self, node: DagNode, change_description: Optional[ChangeDescription] = None) -> None: ...
    def materialize_template(self, node: DagNode) -> None: ...
