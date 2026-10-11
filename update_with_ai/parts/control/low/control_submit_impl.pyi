# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-11T22:09:02Z
# LAST_CHANGED: 2026-10-11T04:05:48Z
# CHANGE: Align implementation with every interface operation: file target submission and resolution
# CODE_HASH: 176934aaf307
# SPEC_QA_AUDIT: 2026-10-11T22:09:02Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation specification for control_submit_impl."""

from typing import Optional, Sequence, Tuple
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import agent_file_alias
import agent_node_config
import control_submit
import control_verification
import dag_storage
import src_metadata


@singleton_type("agent_session")
class SubmissionCoordinator(
    control_submit.SubmissionCoordinator,
    InTier[AgentSessionTier],
):
    """Implementation of submission coordinator.

    GROUNDING:
    - Realizes submission gating by verifying check outcomes from the VerificationEvaluator
      collaborator, validating in-batch dependency cleanliness, enforcing change summary
      constraints against file modifications and auditor role configurations, and mutating
      node cleanliness in the DagStorage collaborator.
    - Realizes file target submission by resolving the submitted target path from text into an
      agent_file_alias.FileAlias through agent_file_alias.AliasManager.convert, validating the
      resolved write permission and directory scope constraints, updating in-band metadata
      headers in the canonical repository through the src_metadata.SourceMetadataCoordinator
      collaborator, and reflecting the update back into the role workspace.
    """

    @operation
    @override
    def submit_target(
        self,
        target_node: dag_storage.DagNode,
        change_summary: Optional[str] = None,
        has_modifications: bool = False,
        in_batch_dependencies: Optional[Sequence[dag_storage.DagNode]] = None,
    ) -> control_submit.SubmissionOutcome:
        """Evaluates submission criteria and commits clean status to storage.

        GROUNDING:
        - Grounded via VerificationEvaluator to ensure checks pass, NodeConfig and RoleConfig
          to inspect auditor roles, modification tracking to validate change summary necessity,
          and DagStorage to update status to clean with the change description.
        """
        ...

    @operation
    @override
    def submit_target_file(
        self,
        target: str,
        summary: Optional[str] = None,
        repo_root: Optional[str] = None,
        workspace_root: Optional[str] = None,
        role_name: Optional[str] = None,
    ) -> control_submit.SubmissionOutcome:
        """Submits a file target after validating file submission constraints.

        GROUNDING:
        - Resolves the submitted target file path and unit name through the implementation's own
          resolution over the supplied repository root, role name, and workspace root, converting
          the target path text into an agent_file_alias.FileAlias through
          agent_file_alias.AliasManager.convert.
        - Rejects verification and test file targets for auditor roles and read-only or
          out-of-scope targets for producer roles through the implementation's own write
          permission check and its own directory scope check over
          agent_file_alias.AliasManager.workspace_root and the resolved target path.
        - Stamps in-band audit tags and updates canonical in-band change metadata through
          src_metadata.SourceMetadataCoordinator.stamp_audit and
          src_metadata.SourceMetadataCoordinator.record_change, then reflects the rewritten
          headers back into the role workspace.
        """
        ...

    @operation
    @override
    def resolve_submit_target(
        self,
        target: str,
        repo_root: str,
        role_name: str,
        dir_scope: str = "staging",
    ) -> Tuple[Optional[str], Optional[str]]:
        """Resolves a target specification to a canonical or workspace file path and unit name.

        GROUNDING:
        - Grounded via the implementation's own path resolution over the supplied repository root,
          role name, and directory scope, returning the canonical and workspace file paths
          alongside the unit name.
        """
        ...

    @operation
    @override
    def parse_unit_from_file_path(
        self, file_path: str, repo_root: str
    ) -> Tuple[str, str, str]:
        """Parses the part directory, unit name, and role name from a file path.

        GROUNDING:
        - Grounded via the implementation's own path parsing over the supplied repository root,
          decomposing the file path into its part directory, unit name, and role name.
        """
        ...
