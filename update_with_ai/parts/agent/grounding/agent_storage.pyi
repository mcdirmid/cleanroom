from dataclasses import dataclass
from typing import Optional, Protocol, Set
from framework import data_type, operation, override, singleton_type
import dag_storage


@data_type
class TaskPrompt(str):
    """Instruction describing the work required to clean a node."""
    ...


@dataclass(frozen=True)
@data_type
class NodeDefinition:
    """Metadata describing task prompts for a node.

    Args:
        node: Target node in the graph.
        task_prompt: Instructions for cleaning the node.
    """
    node: dag_storage.DagNode
    task_prompt: TaskPrompt


@singleton_type("system")
class AgentStorage(dag_storage.DagStorage, Protocol):
    """System service backed by target manifests."""

    @operation
    def get_node_definition(self, node: dag_storage.DagNode) -> Optional[NodeDefinition]:
        """Retrieves metadata definition for a node.

        Args:
            node: Target node in the graph.

        REQUIREMENTS:
        - The agent storage provides task prompts and node definitions for declared nodes.

        GROUNDING_PROVISIONS:
        - action("get_node_definition", Optional[NodeDefinition]): Retrieves node definition to satisfy requirement 4.
        """
        ...

    @operation
    @override
    def get_dependencies(self, node: dag_storage.DagNode) -> Set[dag_storage.DagDependency]:
        """Establishes dependencies that refer to the node's upstream nodes in the graph.

        Args:
            node: Target node in the graph.

        GROUNDING_PROVISIONS:
        - action("get_dependencies", Set[dag_storage.DagDependency]): Retrieves dependencies to satisfy requirement 3.
        """
        ...

    @operation
    @override
    def get_dependents(self, node: dag_storage.DagNode) -> Set[dag_storage.DagNode]:
        """Establishes dependents that refer to downstream nodes depending on it.

        Args:
            node: Target node in the graph.

        GROUNDING_PROVISIONS:
        - action("get_dependents", Set[dag_storage.DagNode]): Retrieves dependents to satisfy requirement 3.
        """
        ...

    @operation
    @override
    def get_messages(self, node: dag_storage.DagNode) -> Set[dag_storage.DagMessage]:
        """Establishes messages explaining why the node requires cleaning.

        Args:
            node: Target node in the graph.

        GROUNDING_PROVISIONS:
        - action("get_messages", Set[dag_storage.DagMessage]): Retrieves messages to satisfy requirement 3.
        """
        ...

    @operation
    @override
    def is_dirty(self, node: dag_storage.DagNode) -> bool:
        """Defines dirty state on a node to indicate that it needs to be cleaned.

        Args:
            node: Target node in the graph.

        GROUNDING_PROVISIONS:
        - action("is_dirty", bool): Returns whether node is dirty to satisfy requirement 3.
        """
        ...

    @operation
    @override
    def register_dependent(self, node: dag_storage.DagNode) -> None:
        """Registers a node as a dependent to all of its non-silent dependencies.

        Args:
            node: Target node to register.

        GROUNDING_PROVISIONS:
        - action("register_dependent", None): Registers dependent relationships to satisfy requirement 3.
        """
        ...

    @operation
    @override
    def clear_dependents(self, node: dag_storage.DagNode) -> None:
        """Clears dependents of a node to avoid stale dependent relationships.

        Args:
            node: Target node to clear dependents for.

        GROUNDING_PROVISIONS:
        - action("clear_dependents", None): Clears dependent relationships to satisfy requirement 3.
        """
        ...

    @operation
    @override
    def add_message(self, message: dag_storage.DagMessage, to: dag_storage.DagNode) -> None:
        """Adds a message to a node explaining why it needs cleaning.

        Args:
            message: Cleaning reason message.
            to: Target node receiving the message.

        GROUNDING_PROVISIONS:
        - action("add_message", None): Adds message to node to satisfy requirement 3.
        """
        ...

    @operation
    @override
    def clear_messages(self, node: dag_storage.DagNode) -> None:
        """Clears messages for a node when it no longer needs cleaning.

        Args:
            node: Target node to clear messages for.

        GROUNDING_PROVISIONS:
        - action("clear_messages", None): Clears messages to satisfy requirement 3.
        """
        ...
