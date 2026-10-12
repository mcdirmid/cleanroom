# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-12T18:21:03Z
# LAST_CHANGED: 2026-10-11T03:36:58Z
# CHANGE: Ground blame resolution in named collaborators and add file-level blame overrides
# CODE_HASH: 09debe45c944
# SPEC_QA_AUDIT: 2026-10-12T18:21:03Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation specification for control_attribution_impl."""

from typing import Any, Optional, Sequence
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import agent_file_alias
import agent_node_config
import control_attribution
import dag_storage
import src_metadata


@singleton_type("agent_session")
class AttributionCoordinator(
    control_attribution.AttributionCoordinator,
    InTier[AgentSessionTier],
):
    """Implementation of attribution coordinator.

    GROUNDING:
    - Realizes blame gating and failure recording by converting blame strings into
      agent_file_alias.BoundFile values through agent_file_alias.AliasManager.convert, intersecting
      those bound files with agent_node_config.NodeConfig.blame_targets_by_node, and verifying
      upstream edges and dependency cleanliness through dag_storage.DagStorage.get_dependencies and
      dag_storage.DagStorage.is_dirty.
    - Persists accepted feedback and culprit dirtiness by constructing dag_storage.FeedbackMessage
      records and invoking dag_storage.DagStorage.add_feedback_message and
      dag_storage.DagStorage.mark_node_dirty.
    - Cascades session status transitions by mutating the coordinator's internal session node
      status mapping, recording the source node as attributed and each in-batch dependent node as
      failed.
    - Executes file-level mutations directly against the canonical repository through
      src_metadata.SourceMetadataCoordinator.append_feedback,
      src_metadata.SourceMetadataCoordinator.mark_dirty, and
      src_metadata.SourceMetadataCoordinator.update_metadata.
    """

    @operation
    @override
    def blame_target(
        self,
        source_node: dag_storage.DagNode,
        blame_target_node: dag_storage.DagNode,
        explanation: str,
        in_batch_dependencies: Optional[Sequence[dag_storage.DagNode]] = None,
        in_batch_dependents: Optional[Sequence[dag_storage.DagNode]] = None,
    ) -> control_attribution.AttributionOutcome:
        """Attributes defect to an upstream dependency and requests reprocessing.

        GROUNDING:
        - Matches the blame target against the owning nodes of the
          agent_node_config.NodeConfig.blame_targets_by_node bound files and against the upstream
          dag_storage.DagDependency nodes returned by dag_storage.DagStorage.get_dependencies for
          the source node, rejecting the attribution when no declared upstream dependency matches.
        - Rejects the attribution when the explanation contains newline or carriage return
          characters, formatting the rejection message from agent_file_alias.FileAlias.relative_path
          values of the configured blame targets.
        - Checks each supplied in-batch dependency through dag_storage.DagStorage.is_dirty and
          rejects the attribution when any of them is not clean.
        - On acceptance, records the explanation as a dag_storage.FeedbackMessage whose content
          carries the explanation and whose target is the culprit node through
          dag_storage.DagStorage.add_feedback_message, marks the culprit dirty through
          dag_storage.DagStorage.mark_node_dirty, and mutates the internal session node status
          mapping to record the source node as attributed and each in-batch dependent node as
          failed.
        """
        ...

    @operation
    @override
    def fail_target(
        self,
        target_node: dag_storage.DagNode,
        explanation: str,
        in_batch_dependents: Optional[Sequence[dag_storage.DagNode]] = None,
    ) -> control_attribution.AttributionOutcome:
        """Records a task failure and fails downstream in-batch dependent nodes.

        GROUNDING:
        - Records the failure diagnostic as a dag_storage.FeedbackMessage through
          dag_storage.DagStorage.add_feedback_message and preserves the target's dirty status
          through dag_storage.DagStorage.mark_node_dirty, passing the explanation as the dirty
          reason.
        - Cascades the failure by mutating the internal session node status mapping for every
          supplied in-batch dependent node.
        """
        ...

    @operation
    @override
    def blame_culprit_file(
        self,
        culprit_file: str,
        critique: str,
        repo_root: Optional[str] = None,
        workspace_root: Optional[str] = None,
        caller_role: Optional[str] = None,
    ) -> control_attribution.AttributionOutcome:
        """Attributes defect blame to an upstream culprit file.

        GROUNDING:
        - Resolves the culprit file through agent_file_alias.AliasManager.convert and
          agent_file_alias.BoundFile.workspace_path, and rejects the blame when the critique
          contains newline or carriage return characters or the culprit file cannot be resolved.
        - Writes accepted feedback directly into the canonical repository by calling
          src_metadata.SourceMetadataCoordinator.append_feedback with the critique and then
          src_metadata.SourceMetadataCoordinator.mark_dirty with the blame reason.
        - Synchronizes the mutated in-band metadata header to disk through
          src_metadata.SourceMetadataCoordinator.update_metadata and constructs the formatted
          acceptance message carried by the attribution outcome.
        """
        ...

    @operation
    @override
    def fail_target_file(
        self,
        target_file: str,
        reason: Optional[str] = None,
        repo_root: Optional[str] = None,
        workspace_root: Optional[str] = None,
    ) -> control_attribution.AttributionOutcome:
        """Records task failure for a target file.

        GROUNDING:
        - Resolves the target file and rejects the recording when the target file cannot be
          resolved.
        - Appends the failure diagnostic through
          src_metadata.SourceMetadataCoordinator.append_feedback and marks the target dirty through
          src_metadata.SourceMetadataCoordinator.mark_dirty.
        - Synchronizes the mutated in-band metadata header to disk through
          src_metadata.SourceMetadataCoordinator.update_metadata and constructs the formatted
          failure message carried by the attribution outcome.
        """
        ...

    @operation
    @override
    def match_blame_target(
        self, node: dag_storage.DagNode, val: Any, val_str: str
    ) -> Optional[agent_file_alias.BoundFile]:
        """Matches a blame target value against configured blame targets for a node.

        GROUNDING:
        - Converts the supplied value through agent_file_alias.AliasManager.convert and intersects
          the resulting agent_file_alias.FileAlias with the
          agent_node_config.NodeConfig.blame_targets_by_node entries configured for the supplied
          node, returning the matching agent_file_alias.BoundFile.
        """
        ...
