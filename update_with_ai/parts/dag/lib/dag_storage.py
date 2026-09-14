from typing import Optional, Protocol, Set
from dataclasses import dataclass


@dataclass(frozen=True)
class Node:
    unit_address: str
    role_address: str = ""


@dataclass(frozen=True)
class Dependency:
    node: Node
    is_silent: bool = False


@dataclass(frozen=True, init=False)
class Message:
    content: str = ""


@dataclass(frozen=True)
class Change(Message):
    content: str = ""


@dataclass(frozen=True)
class Feedback(Message):
    content: str = ""
    target: Optional[Node] = None


class DagStorage(Protocol):
    def get_dependencies(self, node: Node) -> Set[Dependency]: ...

    def get_dependents(self, node: Node) -> Set[Node]: ...

    def get_messages(self, node: Node) -> Set[Message]: ...

    def is_dirty(self, node: Node) -> bool: ...

    def register_dependent(self, node: Node) -> None: ...

    def clear_dependents(self, node: Node) -> None: ...

    def add_message(self, message: Message, to: Node) -> None: ...

    def clear_messages(self, node: Node) -> None: ...
