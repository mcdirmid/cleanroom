from typing import Optional, Protocol, Set
from framework import data_type, operation, singleton_type
from dataclasses import dataclass
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
class AgentStorage(dag_storage.DagStorage, Protocol):
    """
PURPOSE:
Defined as a system service backed by target manifests

INHERITANCE:
- dag_storage.DagStorage: Extends dag storage with target manifest metadata

FRESH_REQUIREMENTS:
- The agent storage maintains nodes, dependencies, reverse dependencies, and pending messages from workspace targets.
- The agent storage provides task prompts and node definitions for declared nodes.
- Declared dependencies marked propagating mark dependent nodes dirty when changed.
"""

    @operation
    def get_node_definition(self, node: dag_storage.Node) -> Optional[NodeDefinition]:
        """
PURPOSE:
Retrieves metadata definition for a node
"""
        ...
