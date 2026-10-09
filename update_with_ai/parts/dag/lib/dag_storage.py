# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-08T00:52:53Z
# LAST_CHANGED: 2026-10-08T00:31:44Z
# CHANGE: Update DagStorage protocol with add_feedback_message, mark_node_dirty, mark_subgraph_clean
# CODE_HASH: 81b13bcfad98
# --- END CLEANROOM METADATA ---

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

    def add_feedback_message(self, node: DagNode, message: FeedbackMessage) -> None: ...

    def add_message(self, message: DagMessage, to: DagNode) -> None: ...

    def mark_node_dirty(self, node: DagNode, reason: Optional[str] = None) -> None: ...

    def mark_subgraph_clean(self, node: DagNode) -> None: ...

    def clear_messages(self, node: DagNode) -> None: ...

    def mark_node_clean(
        self, node: DagNode, change_description: Optional[ChangeDescription] = None
    ) -> None: ...

    def materialize_template(self, node: DagNode) -> None: ...
