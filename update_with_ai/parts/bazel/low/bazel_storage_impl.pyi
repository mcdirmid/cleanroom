"""Bazel storage implementation low-level specification."""

from typing import Optional, Set, Tuple
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
    def record_source_file(self, node: dag_storage.DagNode, path: str) -> None:
        """Associates a declared source file relative path with a node in storage.

        Args:
            node: The node whose source file is recorded.
            path: The workspace-relative path of the source file.

        POSTCONDITIONS:
        - MUST associate the declared source file relative path with the node in storage.
        """
        ...

    @operation
    def store_dependencies(
        self, node: dag_storage.DagNode, dependencies: Set[dag_storage.DagDependency]
    ) -> None:
        """Stores the set of upstream forward dependencies for a node.

        Args:
            node: The node whose forward dependencies are recorded.
            dependencies: The set of upstream forward dependencies.

        POSTCONDITIONS:
        - MUST associate the set of forward dependencies with the node in storage.
        """
        ...

    @operation
    @override
    def get_dependencies(
        self, node: dag_storage.DagNode
    ) -> Set[dag_storage.DagDependency]:
        """Provides the set of upstream forward dependencies for a node.

        Args:
            node: The node whose dependencies are retrieved.

        Returns:
            The set of upstream dependencies for the node.

        POSTCONDITIONS:
        - MUST return the set of upstream forward dependencies for the node.
        """
        ...

    @operation
    def store_silent_source_files(
        self, node: dag_storage.DagNode, paths: Tuple[str, ...]
    ) -> None:
        """Stores the tuple of silent source file relative paths for a node.

        Args:
            node: The node whose silent source files are recorded.
            paths: The tuple of workspace-relative silent source file paths.

        POSTCONDITIONS:
        - MUST associate the silent source file paths with the node in storage.
        """
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
        - WHEN an auditor node has no registered feedback dependencies, MUST raise KeyError.
        - WHEN a declared source file is missing from the workspace root, MUST return true and record a change message to implement the source file.
        - WHEN source file metadata is missing or its last cleaned timestamp is missing, MUST return true.
        - WHEN source file metadata contains unacted feedback entries, MUST return true.
        - WHEN a non-silent forward dependency has a last changed timestamp newer than the node's last cleaned timestamp, MUST return true.
        - WHEN an auditor node has any verified feedback target file missing or any feedback target node dirty, MUST return true.
        - WHEN an auditor node has any verified feedback target file metadata missing, unparseable, or missing the auditor role audit timestamp, MUST return true.
        - WHEN an auditor node has any verified feedback target file with last changed timestamp newer than its audit timestamp, MUST return true.
        - WHEN an auditor node has any non-silent contract dependency with last changed timestamp newer than a verified feedback target file audit timestamp, MUST return true.
        """
        ...

    @operation
    def get_feedback_dependencies(
        self, node: dag_storage.DagNode
    ) -> Set[dag_storage.DagNode]:
        """Returns the set of verified feedback target nodes for an auditor node.

        Args:
            node: The node whose feedback dependencies are retrieved.

        Returns:
            The set of feedback target nodes.

        POSTCONDITIONS:
        - WHEN node is an auditor role without registered feedback dependencies, MUST raise KeyError.
        - MUST return the set of verified feedback target nodes for the auditor node.
        """
        ...

    @operation
    def store_feedback_dependencies(
        self, node: dag_storage.DagNode, feedback_dependencies: Set[dag_storage.DagNode]
    ) -> None:
        """Stores the set of verified feedback target nodes for an auditor node.

        Args:
            node: The auditor node.
            feedback_dependencies: The set of feedback target nodes.

        POSTCONDITIONS:
        - MUST associate the feedback dependencies with the auditor node in storage.
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
        """Clears messages recorded for a node.

        Args:
            node: The node whose messages are cleared.

        POSTCONDITIONS:
        - MUST remove all messages recorded for the node.
        """
        ...

    @operation
    @override
    def mark_node_clean(
        self,
        node: dag_storage.DagNode,
        change_description: Optional[dag_storage.ChangeDescription] = None,
    ) -> None:
        """Marks a node clean in storage, updating metadata and clearing messages.

        Args:
            node: The node to mark clean.
            change_description: Optional description of changes made to the node.

        POSTCONDITIONS:
        - MUST clear all messages for the node.
        - WHEN change_description is provided and node has a source artifact, MUST update the last changed timestamp and change description, and clear unacted feedback.
        - WHEN change_description is omitted and node has a source artifact, MUST update the last cleaned timestamp and clear unacted feedback.
        - WHEN node is an auditor role, MUST stamp audit metadata on all feedback dependencies without updating last changed timestamp.
        - MUST update metadata such that the node is no longer dirty.
        """
        ...

    @operation
    @override
    def materialize_template(self, node: dag_storage.DagNode) -> None:
        """Materializes starter template for a node if its source artifact is missing.

        Args:
            node: The node whose template to materialize.

        POSTCONDITIONS:
        - WHEN node declared source file does not exist, MUST write configured template content to the source path.
        - WHEN node declared source file already exists, MUST preserve existing file content without overwriting.
        """
        ...

    @operation
    def delete_last_cleaned(self, node: dag_storage.DagNode) -> None:
        """Deletes the last cleaned timestamp from a node's source file metadata header.

        Args:
            node: The node whose last cleaned timestamp is deleted.

        POSTCONDITIONS:
        - MUST delete the last cleaned timestamp from the source file metadata header.
        - WHEN node is an auditor role, MUST remove the role audit timestamp from each verified feedback target file metadata.
        """
        ...

