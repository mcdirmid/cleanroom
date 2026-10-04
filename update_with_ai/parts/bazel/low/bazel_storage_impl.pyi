"""Bazel storage implementation low-level specification."""

from typing import Set
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier, SystemTier
import agent_storage
import dag_storage


@singleton_type("system")
class AgentStorage(agent_storage.AgentStorage, InTier[SystemTier]):
    """Realizes in-memory graph indexing and in-band source file metadata persistence for Bazel targets."""

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
        """Indicates whether a node requires cleaning based on missing files, metadata, feedback, or dependency updates.

        Args:
            node: The node whose dirty status is checked.

        Returns:
            True if the node requires cleaning.

        POSTCONDITIONS:
        - WHEN a declared source file is missing from the workspace root, MUST return true and record a change message to implement the source file.
        - WHEN source file metadata is missing or its last cleaned timestamp is missing, MUST return true.
        - WHEN source file metadata contains unacted feedback entries, MUST return true.
        - WHEN a non-silent forward dependency has a last changed timestamp newer than the node's last cleaned timestamp, MUST return true.
        """
        ...

    @operation
    @override
    def add_message(
        self, message: dag_storage.DagMessage, to: dag_storage.DagNode
    ) -> None:
        """Adds a message to a node, updating in-band source metadata with unacted feedback.

        Args:
            message: The message to record.
            to: The target node receiving the message.

        POSTCONDITIONS:
        - WHEN message is a feedback message, MUST append an unacted feedback entry to the target source file metadata.
        """
        ...

    @operation
    @override
    def clear_messages(self, node: dag_storage.DagNode) -> None:
        """Clears messages for a node, updating in-band source metadata on clean.

        Args:
            node: The node whose messages are cleared.

        POSTCONDITIONS:
        - MUST update the last cleaned timestamp and remove unacted feedback entries from source metadata.
        """
        ...

    @operation
    def delete_last_cleaned(self, node: dag_storage.DagNode) -> None:
        """Deletes the last cleaned timestamp from a node's source file metadata header.

        Args:
            node: The node whose last cleaned timestamp is deleted.

        POSTCONDITIONS:
        - MUST delete the last cleaned timestamp from the source file metadata header.
        """
        ...
