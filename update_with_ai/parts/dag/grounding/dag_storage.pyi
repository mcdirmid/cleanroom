from typing import Optional, Protocol, Set
from framework import data_type, operation, override, singleton_type, variant
from dataclasses import dataclass

@singleton_type('system')
class DagStorage(Protocol):
    """
PURPOSE:
Defined as a system service that stores graph structure, node status, and message propagation across nodes
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

    def __init__(self, unit_address: str, role_address: str) -> None:
        ...

    @property
    def unit_address(self) -> str:
        """
PURPOSE:
Unit address identifying the unit of work in graph storage
"""
        ...

    @property
    def role_address(self) -> str:
        """
PURPOSE:
Role address identifying the role of work in graph storage
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
Indicates that a dependency can be silent to preclude change propagation from that dependency
"""
        ...

@dataclass(frozen=True, init=False)
@data_type
class Message:
    """
PURPOSE:
Introduces messages explaining why a node requires cleaning
"""

    @property
    def content(self) -> str:
        """
PURPOSE:
Text content explaining why the node requires cleaning
"""
        ...

@dataclass(frozen=True)
@variant
class Change(Message):
    """
PURPOSE:
Introduces change messages informing of modifications made to upstream dependencies
"""

    def __init__(self, content: str=...) -> None:
        ...

    @property
    @override
    def content(self) -> str:
        """
PURPOSE:
Text content explaining why the node requires cleaning
"""
        ...

@dataclass(frozen=True)
@variant
class Feedback(Message):
    """
PURPOSE:
Introduces feedback messages informing of defects detected by downstream dependents
"""

    def __init__(self, content: str=..., target: Optional[Node]=...) -> None:
        ...

    @property
    def target(self) -> Optional[Node]:
        """
PURPOSE:
Target dependency node addressed by the feedback message
"""
        ...

    @property
    @override
    def content(self) -> str:
        """
PURPOSE:
Text content explaining why the node requires cleaning
"""
        ...
