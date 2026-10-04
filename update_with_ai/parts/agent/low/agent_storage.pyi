"""Agent storage low-level interface specification."""

from dataclasses import dataclass
from typing import NewType, Protocol
from framework import data_type, operation, singleton_type
from support.lib.lifecycle import InTier, SystemTier
import dag_storage

TaskPrompt = NewType("TaskPrompt", str)


@dataclass(frozen=True)
@data_type
class NodeDefinition:
    """Metadata describing task prompts for a node.

    Args:
        task_prompt: The prompt instruction for cleaning the node.
    """
    task_prompt: TaskPrompt


@singleton_type("system")
class AgentStorage(dag_storage.DagStorage, InTier[SystemTier], Protocol):
    """System service extending dag storage with manifest-backed node definitions and prompts."""

    @operation
    def get_node_definition(self, node: dag_storage.DagNode) -> NodeDefinition:
        """Retrieves metadata defining task prompts for a node.

        Args:
            node: The graph node to query.

        Returns:
            The node definition metadata record.

        PRECONDITIONS:
        - A caller supplies a dag node.

        POSTCONDITIONS:
        - MUST provide node definitions for declared nodes.
        """
        ...

    @operation
    def get_task_prompt(self, node: dag_storage.DagNode) -> TaskPrompt:
        """Retrieves the cleaning prompt instruction for a node.

        Args:
            node: The graph node to query.

        Returns:
            The task prompt instruction.

        PRECONDITIONS:
        - A caller supplies a dag node.

        POSTCONDITIONS:
        - MUST provide task prompts for declared nodes.
        """
        ...
