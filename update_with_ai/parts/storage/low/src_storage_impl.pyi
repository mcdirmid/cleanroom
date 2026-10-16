# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:46Z
# LAST_CHANGED: 2026-10-11T04:14:49Z
# CHANGE: Ground target manifest discovery on agent storage alongside in-band metadata parsing
# CODE_HASH: afe4a1e95181
# SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
# --- END CLEANROOM METADATA ---

"""Cleanroom storage implementation low-level specification."""

from typing import Optional, Set, Tuple
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier, SystemTier
import agent_storage
import dag_storage
import file_paths
import src_metadata


@singleton_type("system")
class AgentStorage(agent_storage.AgentStorage, InTier[SystemTier]):
    """Realizes in-memory graph indexing and in-band source file metadata persistence for Cleanroom targets.

    GROUNDING:
    - Realizes agent_storage.AgentStorage over the dag_storage.DagStorage peer by maintaining the
      private _node_definitions mapping from dag_storage.DagNode to agent_storage.NodeDefinition and
      the private _source_paths mapping from dag_storage.DagNode to its declared relative source path.
    - Discovers declared targets from the workspace target manifests through the inherited
      agent_storage.AgentStorage accessors agent_storage.AgentStorage.get_node_definition and
      agent_storage.AgentStorage.get_task_prompt, which read each manifest-declared
      agent_storage.NodeDefinition and its agent_storage.TaskPrompt from the private
      _node_definitions mapping, and parses the declared source file in-band header through
      src_metadata.SourceMetadataCoordinator.extract_metadata into a src_metadata.FileMetadata
      record.
    - Maintains task prompts without a separate store by exposing
      agent_storage.NodeDefinition.task_prompt from the _node_definitions entries, so
      agent_storage.AgentStorage.get_task_prompt never reads the source file on disk.
    - Maintains the private _dependencies mapping of dag_storage.DagDependency edges and the private
      _silent_source_files mapping of silent source paths, filtering dirty propagation with the
      dag_storage.DagDependency.is_silent flag.
    - Maintains the private _feedback_dependencies mapping from an auditor dag_storage.DagNode to its
      verified feedback target dag_storage.DagNode set, plus the private _messages mapping of
      dag_storage.DagMessage diagnostics surfaced through dag_storage.DagStorage.get_messages.
    - Resolves every declared source path against the workspace root through
      file_paths.FilePathManager.create_workspace_path, file_paths.FilePathManager.create_absolute_path,
      and file_paths.FilePathManager.resolve_path, then observes and rewrites the resolved host file
      through the src_metadata.SourceMetadataCoordinator collaborator and the filesystem_ext host path
      existence, read, and write mechanics.
    """

    @operation
    @override
    def get_node_definition(
        self, node: dag_storage.DagNode
    ) -> agent_storage.NodeDefinition:
        """Retrieves in-memory node definition for a node.

        GROUNDING:
        - Reads the agent_storage.NodeDefinition recorded in the private _node_definitions mapping
          under the supplied dag_storage.DagNode key and returns it without consulting src_metadata or
          the source file on disk.
        """
        ...

    @operation
    def store_node_definition(
        self, node: dag_storage.DagNode, definition: agent_storage.NodeDefinition
    ) -> None:
        """Stores in-memory node definition for a node.

        POSTCONDITIONS:
        - MUST record the node definition mapped to the node in storage.

        GROUNDING:
        - Writes the supplied agent_storage.NodeDefinition into the private _node_definitions mapping
          under the dag_storage.DagNode key, replacing any previously recorded definition so that a
          subsequent agent_storage.AgentStorage.get_task_prompt observes the new task prompt.
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
        - Writes the workspace-relative path string into the private _source_paths mapping under the
          dag_storage.DagNode key, held as an unresolved relative path that
          file_paths.FilePathManager.create_workspace_path validates before
          file_paths.FilePathManager.resolve_path joins it to the workspace root.
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
        - Replaces the private _dependencies entry for the dag_storage.DagNode with the supplied
          dag_storage.DagDependency set, preserving each edge's dag_storage.DagDependency.is_silent
          flag so silent edges can be filtered out of dirty propagation.
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
        - Returns the dag_storage.DagDependency set held in the private _dependencies mapping for the
          dag_storage.DagNode, yielding an empty set when no edges were recorded.
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
        - Writes the tuple of silent workspace-relative paths into the private _silent_source_files
          mapping under the dag_storage.DagNode key so that dependency propagation skips those
          declared artifacts when evaluating dirty status.
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
        - WHEN an auditor node has no registered feedback dependency entry, MUST raise KeyError.
        - WHEN an auditor node has an empty registered feedback dependency set and any non-silent forward dependency is dirty, MUST return true.
        - WHEN the declared source file is missing from the workspace root, MUST return true and record a change message to implement the source file.
        - WHEN source file metadata is missing or unparseable, MUST return true.
        - WHEN the source file metadata last cleaned timestamp is missing, MUST return true.
        - WHEN source file metadata contains unacted feedback entries, MUST return true and synthesize feedback messages for those entries.
        - WHEN source file metadata contains a dirty tag, MUST return true and synthesize a change message.
        - WHEN a non-silent forward dependency has a last changed timestamp strictly newer than the node's last cleaned timestamp, MUST return true and synthesize a change message.
        - WHEN any verified feedback target file of an auditor node is missing from the workspace root, MUST return true.
        - WHEN any verified feedback target node of an auditor node evaluates as dirty, MUST return true.
        - WHEN any verified feedback target file metadata of an auditor node is missing, MUST return true.
        - WHEN any verified feedback target file metadata of an auditor node is unparseable, MUST return true.
        - WHEN any verified feedback target file of an auditor node is missing the auditor role audit timestamp, MUST return true.
        - WHEN any verified feedback target file of an auditor node has a last changed timestamp strictly newer than its auditor role audit timestamp, MUST return true.
        - WHEN any non-silent contract dependency of an auditor node has a last changed timestamp strictly newer than a verified feedback target file audit timestamp, MUST return true.

        GROUNDING:
        - Resolves the declared source path by validating the private _source_paths relative string
          with file_paths.FilePathManager.create_workspace_path and joining it to the workspace root
          with file_paths.FilePathManager.resolve_path, then tests existence with the filesystem_ext
          host path checks.
        - Parses the resolved header with src_metadata.SourceMetadataCoordinator.extract_metadata
          into a src_metadata.FileMetadata record and treats a missing or unparseable record, a missing
          src_metadata.FileMetadata.last_cleaned, a populated src_metadata.FileMetadata.feedback list,
          or a populated src_metadata.FileMetadata.dirty reason as dirty.
        - Iterates the private _dependencies edges for the dag_storage.DagNode, skipping edges whose
          dag_storage.DagDependency.is_silent flag is set, and compares the
          src_metadata.FileMetadata.last_changed of each dag_storage.DagDependency.node against the
          node's own src_metadata.FileMetadata.last_cleaned.
        - Detects auditor nodes from the dag_storage.DagNode.role_address, reads the private
          _feedback_dependencies registry, raises KeyError when no entry exists, and otherwise
          delegates to the recorded forward dependencies when the registry entry is empty.
        - Reads each verified feedback target through the private _source_paths mapping and
          src_metadata.SourceMetadataCoordinator.extract_metadata to compare
          src_metadata.FileMetadata.last_changed against the auditor role entry in
          src_metadata.FileMetadata.audits and to consult dag_storage.DagStorage.is_dirty.
        - Mutates the private _messages mapping with synthesized dag_storage.ChangeMessage and
          dag_storage.FeedbackMessage records so the recorded diagnostics surface through
          dag_storage.DagStorage.get_messages.
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
        - WHEN an auditor node has no registered feedback dependency entry, MUST raise KeyError.
        - MUST return the set of verified feedback target nodes for the auditor node.

        GROUNDING:
        - Returns the verified feedback target dag_storage.DagNode set held in the private
          _feedback_dependencies mapping under the auditor dag_storage.DagNode key.
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
        - Writes the verified feedback target dag_storage.DagNode set into the private
          _feedback_dependencies mapping under the auditor dag_storage.DagNode key.
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
        - Resolves the blamed dag_storage.DagNode through the private _source_paths mapping and
          file_paths.FilePathManager.resolve_path, then appends the
          dag_storage.FeedbackMessage.content as an unacted entry with
          src_metadata.SourceMetadataCoordinator.append_feedback, caching the message in the private
          _messages mapping when the blamed node declares no source artifact.
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
        - Dispatches on the dag_storage.DagMessage runtime variant: dag_storage.FeedbackMessage
          content is appended to the addressed target header as an unacted entry through
          src_metadata.SourceMetadataCoordinator.append_feedback, while dag_storage.ChangeMessage
          content is written as a dirty tag through
          src_metadata.SourceMetadataCoordinator.update_metadata with clear_last_cleaned set true,
          falling back to the private _messages mapping for target nodes without a source artifact.
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
        - MUST record a dirty tag in the node's in-band source metadata.
        - MUST preserve the node's change description and last changed timestamp.
        - WHEN reason is provided, MUST record the supplied reason as the dirty tag content.
        - WHEN node is an auditor role, MUST remove the role audit timestamp from each verified feedback target file metadata.

        GROUNDING:
        - Rewrites the resolved source header through
          src_metadata.SourceMetadataCoordinator.update_metadata with clear_last_cleaned set true and
          dirty set to the supplied reason, leaving src_metadata.FileMetadata.change_summary and
          src_metadata.FileMetadata.last_changed untouched.
        - For an auditor node, rebuilds each verified feedback target's
          src_metadata.FileMetadata.audits mapping without the auditor role entry and writes it back
          through src_metadata.SourceMetadataCoordinator.update_metadata so that only the auditor role
          audit timestamp is removed.
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
        - Walks the private _dependencies edges from the supplied dag_storage.DagNode, mirroring
          dag_storage.DagStorage.get_dependencies, materializes any missing source artifact through
          the materialize_template member, and marks every visited node clean through mark_node_clean.
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
        - Removes the cached dag_storage.DagMessage set recorded in the private _messages mapping for
          the dag_storage.DagNode so that dag_storage.DagStorage.get_messages subsequently reports no
          messages for that node.
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
        - WHEN the node has a source artifact, MUST update the last cleaned timestamp to the current timestamp and clear unacted feedback and dirty tags.
        - WHEN change_description is provided, MUST update the last changed timestamp and record the change description.
        - WHEN change_description is omitted, MUST preserve the existing last changed timestamp.
        - WHEN node is an auditor role, MUST stamp the auditor role audit timestamp on every verified feedback target file without altering the target last changed timestamp.
        - MUST update metadata such that the node is no longer dirty.

        GROUNDING:
        - Clears the private _messages entry for the dag_storage.DagNode and rewrites the resolved
          source header through src_metadata.SourceMetadataCoordinator.update_metadata, passing
          last_cleaned, clear_feedback, and clear_dirty, and additionally passing last_changed and
          change_summary when the change description is supplied.
        - For an auditor node, walks the private _feedback_dependencies target set and stamps the
          auditor role timestamp on each resolved target header with
          src_metadata.SourceMetadataCoordinator.stamp_audit, which advances only the target
          src_metadata.FileMetadata.last_cleaned.
        """
        ...

    @operation
    @override
    def materialize_template(self, node: dag_storage.DagNode) -> None:
        """Materializes starter template for a node if its source artifact is missing.

        Args:
            node: The node whose template to materialize.

        POSTCONDITIONS:
        - WHEN the declared source file is missing from the workspace root, MUST write the configured template content for the node to the declared source path.
        - WHEN the declared source file is missing from the workspace root and the node configures a role template command instead of template content, MUST execute that command to produce the declared source file.
        - WHEN the declared source file already exists, MUST preserve the existing file content without overwriting.

        GROUNDING:
        - Resolves the declared source path through the private _source_paths mapping and
          file_paths.FilePathManager.resolve_path, checks existence with the filesystem_ext host path
          checks, then writes the configured template content through the filesystem_ext host path
          write mechanics with missing parent directories created, or otherwise executes the
          configured role template command; an existing file is left byte-identical.
        """
        ...

    @operation
    def delete_last_cleaned(self, node: dag_storage.DagNode) -> None:
        """Deletes the last cleaned timestamp from a node's source file metadata header.

        Args:
            node: The node whose last cleaned timestamp is deleted.

        POSTCONDITIONS:
        - MUST delete the last cleaned timestamp from the source file metadata header.
        - MUST mark the node dirty so that is_dirty returns true.
        - MUST preserve the change description and last changed timestamp.
        - WHEN node is an auditor role, MUST remove the role audit timestamp from each verified feedback target file metadata.

        GROUNDING:
        - Calls src_metadata.SourceMetadataCoordinator.delete_last_cleaned on the resolved source file
          and leaves src_metadata.FileMetadata.change_summary and
          src_metadata.FileMetadata.last_changed unchanged so that the node evaluates as dirty.
        - For an auditor node, removes the auditor role entry from each verified feedback target's
          src_metadata.FileMetadata.audits mapping through
          src_metadata.SourceMetadataCoordinator.update_metadata.
        """
        ...
