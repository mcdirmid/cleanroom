# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
# LAST_CHANGED: 2026-10-08T00:46:00Z
# CHANGE: Define src_storage_impl low-level specification
# CODE_HASH: 8c4de6fac767
# LOW_QA_AUDIT: 2026-10-09T21:19:01Z
# --- END CLEANROOM METADATA ---

"""Cleanroom storage implementation low-level specification."""

from typing import Optional, Set, Tuple
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier, SystemTier
from update_with_ai.parts.agent.lib import agent_storage
from update_with_ai.parts.dag.lib import dag_storage
import file_paths
import src_metadata


@singleton_type("system")
class AgentStorage(agent_storage.AgentStorage, InTier[SystemTier]):
    """Realizes in-memory graph indexing and in-band source file metadata persistence for Cleanroom targets.

    GROUNDING:
    - Realizes agent_storage and dag_storage by indexing target definitions and dependencies in memory while persisting dirty status and feedback in in-band source headers via src_metadata.
    """

    @operation
    @override
    def get_node_definition(
        self, node: dag_storage.DagNode
    ) -> agent_storage.NodeDefinition:
        """Retrieves in-memory node definition for a node.

        GROUNDING:
        - Returns the NodeDefinition cached in memory for the given DagNode.
        """
        ...

    @operation
    @override
    def store_node_definition(
        self, node: dag_storage.DagNode, definition: agent_storage.NodeDefinition
    ) -> None:
        """Stores in-memory node definition for a node.

        GROUNDING:
        - Records the NodeDefinition in the in-memory dictionary mapped by DagNode.
        """
        ...

    @operation
    def record_source_file(self, node: dag_storage.DagNode, path: str) -> None:
        """Associates a declared source file relative path with a node in storage.

        Args:
            node: The node whose source file is recorded.
            path: The workspace-relative path of the source file.

        POSTCONDITIONS:
        - MUST associate the declared source file relative path with the node in storage.

        GROUNDING:
        - Maps the DagNode to its workspace-relative primary source file path in memory.
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

        GROUNDING:
        - Records the forward DagDependency set for the node in the in-memory dependency index.
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

        GROUNDING:
        - Retrieves the recorded set of forward DagDependency edges from the in-memory dependency index.
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

        GROUNDING:
        - Records the tuple of silent source file relative paths for the node in memory.
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
        - WHEN an auditor node has empty registered feedback dependencies and forward dependencies, MUST delegate dirty evaluation to its forward dependencies.
        - WHEN a declared source file is missing from the workspace root, MUST return true and record a change message to implement the source file.
        - WHEN source file metadata is missing or its last cleaned timestamp is missing, MUST return true.
        - WHEN source file metadata contains unacted feedback entries, MUST return true.
        - WHEN source file metadata contains a dirty tag, MUST return true.
        - WHEN a non-silent forward dependency has a last changed timestamp newer than the node's last cleaned timestamp, MUST return true.
        - WHEN an auditor node has any verified feedback target file missing or any feedback target node dirty, MUST return true.
        - WHEN an auditor node has any verified feedback target file metadata missing, unparseable, or missing the auditor role audit timestamp, MUST return true.
        - WHEN an auditor node has any verified feedback target file with last changed timestamp newer than its audit timestamp, MUST return true.
        - WHEN an auditor node has any non-silent contract dependency with last changed timestamp newer than a verified feedback target file audit timestamp, MUST return true.

        GROUNDING:
        - Evaluates dirty state by inspecting source file existence via file_paths, parsing in-band headers with src_metadata, and comparing dependency change timestamps.
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

        GROUNDING:
        - Retrieves the verified feedback target nodes mapped to the auditor node in memory.
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

        GROUNDING:
        - Associates verified feedback target nodes with the auditor node in memory.
        """
        ...

    @operation
    @override
    def add_feedback_message(
        self, node: dag_storage.DagNode, message: dag_storage.FeedbackMessage
    ) -> None:
        """Adds a feedback message blaming a dependency target node.

        Args:
            node: The dependency target node receiving the feedback message.
            message: The feedback message to record for the node.

        POSTCONDITIONS:
        - MUST append an unacted feedback entry to the target source file metadata.

        GROUNDING:
        - Appends unacted feedback to the blamed node source header via src_metadata.
        """
        ...

    @operation
    @override
    def add_message(
        self, message: dag_storage.DagMessage, to: dag_storage.DagNode
    ) -> None:
        """Adds a message to a node, updating in-band source metadata.

        Args:
            message: The message to record.
            to: The target node receiving the message.

        POSTCONDITIONS:
        - WHEN message is a feedback message, MUST append an unacted feedback entry to the target source file metadata.
        - WHEN message is a change message and target source file exists, MUST update target source file in-band metadata with the change description as a dirty tag, clearing its last cleaned status.

        GROUNDING:
        - Updates target source file in-band metadata via src_metadata or caches diagnostic DagMessage in memory.
        """
        ...

    @operation
    @override
    def mark_node_dirty(
        self, node: dag_storage.DagNode, reason: Optional[str] = ...
    ) -> None:
        """Marks a node dirty by clearing clean status and recording dirty reason.

        Args:
            node: The node to mark dirty.
            reason: Optional reason explaining why the node is marked dirty.

        POSTCONDITIONS:
        - MUST mark the node dirty so that is_dirty returns true.
        - MUST clear the last cleaned status in the node's in-band metadata.
        - WHEN reason is provided, MUST record the dirty tag in source metadata.
        - WHEN node is an auditor role, MUST remove the role audit timestamp from each verified feedback target file metadata.

        GROUNDING:
        - Clears the last cleaned timestamp and updates dirty tag in source metadata via src_metadata.
        """
        ...

    @operation
    @override
    def mark_subgraph_clean(self, node: dag_storage.DagNode) -> None:
        """Marks the target node and all reachable dependencies in its subgraph clean.

        Args:
            node: The root node of the subgraph to mark clean.

        POSTCONDITIONS:
        - MUST mark the target node clean.
        - MUST mark all reachable dependencies of the node clean.
        - MUST materialize missing templates for all nodes in the subgraph.

        GROUNDING:
        - Traverses dependencies using get_dependencies, materializes missing templates, and marks each node clean.
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

        GROUNDING:
        - Removes diagnostic messages cached in memory for the specified DagNode.
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
        - WHEN change_description is provided and node has a source artifact, MUST update the last changed timestamp and change description, and clear unacted feedback and dirty tag.
        - WHEN change_description is omitted and node has a source artifact, MUST update the last cleaned timestamp and clear unacted feedback and dirty tag.
        - WHEN node is an auditor role, MUST stamp audit metadata on all feedback dependencies without updating last changed timestamp.
        - MUST update metadata such that the node is no longer dirty.

        GROUNDING:
        - Updates in-band timestamps, removes feedback and dirty tags via src_metadata, and stamps audit metadata on feedback dependencies.
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

        GROUNDING:
        - Writes configured template content to the source path via file_paths if the source file does not exist on disk.
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

        GROUNDING:
        - Clears the last cleaned timestamp in the source metadata header via src_metadata, marking the node dirty.
        """
        ...
