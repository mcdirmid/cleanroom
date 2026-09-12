from typing import Optional, Protocol, Set
from framework import data_type, operation, override, singleton_type
from dataclasses import dataclass
import bazel_node_id_utils
import dag_storage

@data_type
class TaskPrompt(str):
    """
PURPOSE:
Instruction describing the work required to clean a node
"""
    ...

@dataclass(frozen=True)
@data_type
class NodeDefinition:
    """
PURPOSE:
Metadata describing task prompts for a node
"""

    def __init__(self, node: dag_storage.Node, task_prompt: TaskPrompt) -> None:
        ...

    @property
    def node(self) -> dag_storage.Node:
        """
PURPOSE:
Target node in the graph
"""
        ...

    @property
    def task_prompt(self) -> TaskPrompt:
        """
PURPOSE:
Instructions for cleaning the node
"""
        ...

@singleton_type('system')
class BazelGraphStorage(dag_storage.DagStorage, Protocol):
    """
PURPOSE:
Defined as a system service backed by target manifests

INHERITANCE:
- dag_storage.DagStorage: Extends dag storage with target manifest metadata

FRESH_REQUIREMENTS:
- The bazel graph storage maintains nodes, dependencies, reverse dependencies, and pending messages from workspace targets.
- The bazel graph storage provides task prompts and node definitions for declared nodes.
- Declared dependencies marked propagating mark dependent nodes dirty when changed.
- The bazel graph storage persists pending messages and reverse dependencies across package directories resolved by the bazel node identifier utility from bazel node id utils.
"""

    @operation
    def get_node_definition(self, node: dag_storage.Node) -> Optional[NodeDefinition]:
        """
PURPOSE:
Retrieves metadata definition for a node
"""
        ...

    @operation
    @override
    def get_dependencies(self, node: dag_storage.Node) -> Set[dag_storage.Dependency]:
        """
PURPOSE:
Establishes dependencies that refer to the node's upstream nodes in the graph
"""
        ...

    @operation
    @override
    def get_dependents(self, node: dag_storage.Node) -> Set[dag_storage.Node]:
        """
PURPOSE:
Establishes dependents that refer to downstream nodes depending on it
"""
        ...

    @operation
    @override
    def get_messages(self, node: dag_storage.Node) -> Set[dag_storage.Message]:
        """
PURPOSE:
Establishes messages explaining why the node requires cleaning
"""
        ...

    @operation
    @override
    def is_dirty(self, node: dag_storage.Node) -> bool:
        """
PURPOSE:
Defines dirty state on a node to indicate that it needs to be cleaned

INHERITED_REQUIREMENTS:
- [DagStorage] A node is dirty if, but not only if, it has messages.
"""
        ...

    @operation
    @override
    def register_dependent(self, node: dag_storage.Node) -> None:
        """
PURPOSE:
Provides that a node can be registered as a dependent to all of its non-silent dependencies

INHERITED_REQUIREMENTS:
- [DagStorage] Registering a node as a dependent adds the node to the dependents of all of its non-silent dependencies.
"""
        ...

    @operation
    @override
    def clear_dependents(self, node: dag_storage.Node) -> None:
        """
PURPOSE:
Provides that the dependents of a node can be cleared to avoid stale dependent relationships

INHERITED_REQUIREMENTS:
- [DagStorage] Clearing the dependents of a node empties all recorded dependents for that node.
"""
        ...

    @operation
    @override
    def add_message(self, message: dag_storage.Message, to: dag_storage.Node) -> None:
        """
PURPOSE:
Provides that messages can be added to a node to inform on why it needs to be cleaned

INHERITED_REQUIREMENTS:
- [DagStorage] Adding a message to a node records the message for that node.
"""
        ...

    @operation
    @override
    def clear_messages(self, node: dag_storage.Node) -> None:
        """
PURPOSE:
Provides that messages of a node can be cleared to inform that it no longer needs to be cleaned

INHERITED_REQUIREMENTS:
- [DagStorage] Clearing messages for a node removes all recorded messages for that node.
"""
        ...
