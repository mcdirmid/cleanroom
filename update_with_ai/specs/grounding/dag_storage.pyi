from typing import Protocol, Set
from framework import data_type, operation, singleton_type, variant
from dataclasses import dataclass

@singleton_type('system')
class DagStorage(Protocol):
    """
PURPOSE:
Defined as a system service that maintains node state, including its graph structure and change propagation
"""

    @operation
    def get_dependencies(self, node: Node) -> Set[Dependency]:
        """
PURPOSE:
Establishes dependencies that refer to the node's upstream nodes in the graph
"""
        ...

    @operation
    def get_dependents(self, node: Node) -> Set[Node]:
        """
PURPOSE:
Establishes dependents that refer to downstream nodes depending on it
"""
        ...

    @operation
    def get_messages(self, node: Node) -> Set[Message]:
        """
PURPOSE:
Establishes messages explaining why the node requires cleaning
"""
        ...

    @operation
    def is_dirty(self, node: Node) -> bool:
        """
PURPOSE:
Defines dirty state on a node to indicate that it needs to be cleaned

FRESH_REQUIREMENTS:
- A node is dirty if, but not only if, it has messages.
"""
        ...

    @operation
    def register_dependent(self, node: Node) -> None:
        """
PURPOSE:
Provides that a node can be registered as a dependent to all of its non-silent dependencies

FRESH_REQUIREMENTS:
- Registering a node as a dependent adds the node to the dependents of all of its non-silent dependencies.
"""
        ...

    @operation
    def clear_dependents(self, node: Node) -> None:
        """
PURPOSE:
Provides that the dependents of a node can be cleared to avoid stale dependent relationships

FRESH_REQUIREMENTS:
- Clearing the dependents of a node empties all recorded dependents for that node.
"""
        ...

    @operation
    def add_message(self, message: Message, to: Node) -> None:
        """
PURPOSE:
Provides that messages can be added to a node to inform on why it needs to be cleaned

FRESH_REQUIREMENTS:
- Adding a message to a node records the message for that node.
"""
        ...

    @operation
    def clear_messages(self, node: Node) -> None:
        """
PURPOSE:
Provides that messages of a node can be cleared to inform that it no longer needs to be cleaned

FRESH_REQUIREMENTS:
- Clearing messages for a node removes all recorded messages for that node.
"""
        ...

@dataclass(frozen=True)
@data_type
class Node:
    """
PURPOSE:
Introduces a node to identify a discrete unit of work in the graph
"""

    def __init__(self, address: str) -> None:
        ...

    @property
    def address(self) -> str:
        """
PURPOSE:
Unique address identifying the node in graph storage
"""
        ...

@dataclass(frozen=True)
@data_type
class Dependency:
    """
PURPOSE:
Introduces a dependency relationship referring to an upstream node in the graph
"""

    def __init__(self, node: Node, is_silent: bool=...) -> None:
        ...

    @property
    def node(self) -> Node:
        """
PURPOSE:
Establishes that each dependency references an upstream target node
"""
        ...

    @property
    def is_silent(self) -> bool:
        """
PURPOSE:
Indicates that a dependency can be silent when the dependent node does not depend on its content
"""
        ...

@dataclass(frozen=True, init=False)
@data_type
class Message:
    """
PURPOSE:
Introduces messages explaining why a node requires cleaning
"""
    ...

@dataclass(frozen=True)
@variant
class Change(Message):
    """
PURPOSE:
Introduces change messages informing of modifications made to upstream dependencies
"""

    def __init__(self) -> None:
        ...

@dataclass(frozen=True)
@variant
class Feedback(Message):
    """
PURPOSE:
Introduces feedback messages informing of issues detected by downstream dependents
"""

    def __init__(self) -> None:
        ...
