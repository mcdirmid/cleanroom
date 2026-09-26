# Requirements specified in dag_storage.pyi
from typing import Optional, Protocol, Set
from dataclasses import dataclass


@dataclass(frozen=True)
class DagNode:
    unit_address: str
    role_address: str = ""


@dataclass(frozen=True)
class DagDependency:
    node: DagNode
    is_silent: bool = False


@dataclass(frozen=True, init=False)
class DagMessage:
    content: str = ""


@dataclass(frozen=True)
class ChangeMessage(DagMessage):
    content: str = ""


@dataclass(frozen=True)
class FeedbackMessage(DagMessage):
    content: str = ""
    target: Optional[DagNode] = None



class DagStorage(Protocol):
    def get_dependencies(self, node: DagNode) -> Set[DagDependency]: ...

    def get_dependents(self, node: DagNode) -> Set[DagNode]: ...

    def get_messages(self, node: DagNode) -> Set[DagMessage]: ...

    def is_dirty(self, node: DagNode) -> bool: ...

    def register_dependent(self, node: DagNode) -> None: ...

    def clear_dependents(self, node: DagNode) -> None: ...

    def add_message(self, message: DagMessage, to: DagNode) -> None: ...

    def clear_messages(self, node: DagNode) -> None: ...
