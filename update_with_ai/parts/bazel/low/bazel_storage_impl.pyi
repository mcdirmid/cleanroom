"""Bazel storage implementation low-level specification."""

from typing import Set
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier, SystemTier
import agent_storage
import dag_storage


@singleton_type("system")
class AgentStorage(agent_storage.AgentStorage, InTier[SystemTier]):
    """Realizes in-memory graph indexing and protobuf text message persistence for Bazel targets."""

    @operation
    @override
    def get_node_definition(
        self, node: dag_storage.DagNode
    ) -> agent_storage.NodeDefinition:
        ...

    @operation
    @override
    def store_node_definition(
        self, node: dag_storage.DagNode, definition: agent_storage.NodeDefinition
    ) -> None:
        ...

    @operation
    @override
    def is_dirty(self, node: dag_storage.DagNode) -> bool:
        """Indicates whether a node requires cleaning based on messages or missing source file.

        Args:
            node: The node whose dirty status is checked.

        Returns:
            True if the node has messages or missing source file.

        POSTCONDITIONS:
        - WHEN a node has messages or its declared source file is missing from the workspace root, MUST return true.
        - WHEN a declared source file is missing from the workspace root, MUST record a change message to implement the source file.
        """
        ...

    @operation
    @override
    def add_message(
        self, message: dag_storage.DagMessage, to: dag_storage.DagNode
    ) -> None:
        """Adds a message to a node and persists it to package message storage.

        Args:
            message: The message to record.
            to: The target node receiving the message.

        POSTCONDITIONS:
        - MUST serialize pending messages into package .update_with_ai.textproto files.
        """
        ...

    @operation
    @override
    def register_dependent(self, node: dag_storage.DagNode) -> None:
        """Registers a node as a dependent across its non-silent dependencies.

        Args:
            node: The node to register as a dependent.

        POSTCONDITIONS:
        - MUST serialize reverse dependencies into package .update_with_ai.textproto files.
        - MUST exclude silent dependencies when serializing reverse dependencies.
        """
        ...
