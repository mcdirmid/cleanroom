# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-11T22:09:03Z
# LAST_CHANGED: 2026-10-11T04:14:51Z
# CHANGE: Filter silent cross-role dependencies, expand star-role contracts, and fail loud on unknown roles
# CODE_HASH: ff4c4d707a26
# SPEC_QA_AUDIT: 2026-10-11T22:09:03Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation specification for workspace_work_impl."""

from typing import Optional, Sequence
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import workspace_work
import control_work_scheduler
import src_metadata
import dag_storage
import workspace_registry


@singleton_type("agent_session")
class WorkspaceWorkManager(
    workspace_work.WorkspaceWorkManager,
    InTier[AgentSessionTier],
):
    """Realizes work discovery across directory scopes and pending buffer tracking.

    GROUNDING:
    - Realizes work discovery by delegating directory-scoped scheduling to
      control_work_scheduler.WorkScheduler.schedule_work and ordering candidates through
      control_work_scheduler.WorkScheduler.compute_role_precedence, materializing starter
      templates via dag_storage.DagStorage.materialize_template, checking target metadata via
      src_metadata.SourceMetadataCoordinator.extract_metadata, evaluating auditor unit
      dirtiness across all feedback targets, evaluating producer unit dirtiness across implicit
      and star role dependencies, and managing pending work state in
      .cleanroom_pending_work.json.
    - Grounds companion contract resolution and cross-unit dependency filtering on
      workspace_registry.WorkspaceRegistry.resolve_role_definition and
      workspace_registry.WorkspaceRegistry.list_roles, reading
      workspace_registry.RoleDefinition.writable_file_patterns,
      workspace_registry.RoleDefinition.star_role_deps, and
      workspace_registry.RoleDefinition.silent_cross_role_deps to expand dynamically defined
      star-role specification contracts for the active role and to filter out silent cross-role
      dependencies from resolved contract files, and letting an undeclared role or unmatched
      target path raise an explicit exception through the registry lookup without synthesizing a
      substitute role or path.
    """

    @operation
    @override
    def get_pending_work(self, workspace_dir: str) -> Sequence[str]:
        """Reads target paths from local pending work buffer.

        GROUNDING:
        - Reads and parses JSON array from .cleanroom_pending_work.json.
        """
        ...

    @operation
    @override
    def clear_pending_work(self, workspace_dir: str) -> None:
        """Removes local pending work buffer file if present.

        GROUNDING:
        - Deletes .cleanroom_pending_work.json from workspace directory if it exists.
        """
        ...

    @operation
    @override
    def set_pending_work(self, workspace_dir: str, targets: Sequence[str]) -> None:
        """Records pending target paths into local buffer file.

        GROUNDING:
        - Writes targets sequence to .cleanroom_pending_work.json or removes file when empty.
        """
        ...

    @operation
    @override
    def remove_pending_target(self, workspace_dir: str, submitted_target: str) -> None:
        """Removes a submitted target from local pending work buffer.

        GROUNDING:
        - Filters out target path or stem matching submitted target without wiping non-matching targets.
        """
        ...

    @operation
    @override
    def is_pending_target_dirty(
        self,
        target_path: str,
        workspace_dir: str,
        main_root: Optional[str] = None,
        role_name: Optional[str] = None,
    ) -> bool:
        """Checks whether a pending target file is still dirty across local and main workspaces.

        GROUNDING:
        - Checks target metadata via src_metadata.SourceMetadataCoordinator.extract_metadata across
          local workspace and main repository, evaluating auditor role targets across all
          configured feedback role targets, and evaluating producer targets across implicit role
          dependencies and star role dependencies.
        """
        ...

    @operation
    @override
    def compute_role_work_queue(
        self,
        role_name: str,
        dir_scope: str,
        repo_root: str,
    ) -> tuple[Sequence[workspace_work.WorkQueueItem], Sequence[workspace_work.WorkQueueItem]]:
        """Computes ready and blocked dirty units directly from build manifests and metadata.

        GROUNDING:
        - Scans part directories in scope, evaluates auditor units across all feedback role dependencies,
          evaluates producer units across implicit role dependencies and star role dependencies,
          checks dependencies, sorts ready tasks topologically, and materializes starter templates via
          dag_storage.DagStorage.materialize_template for missing ready files.
        """
        ...

    @operation
    @override
    def evaluate_work(
        self,
        dir_scope: str,
        role_name: str,
        workspace_dir: Optional[str] = None,
        force: bool = False,
    ) -> workspace_work.WorkQueueSummary:
        """Evaluates dirty units in scope and returns work queue summary.

        POSTCONDITIONS:
        - WHEN the supplied role is undeclared, MUST raise an explicit exception without substituting a fallback role.
        - WHEN a target path matches no configured file pattern of the supplied role, MUST raise an explicit exception without synthesizing a substitute path.

        GROUNDING:
        - Checks pending target dirtiness via src_metadata, schedules tasks via
          control_work_scheduler.WorkScheduler.schedule_work with dir_scope, records ready targets,
          and formats the WorkQueueSummary.
        - Resolves the active workspace_registry.RoleDefinition through
          workspace_registry.WorkspaceRegistry.resolve_role_definition and lets an undeclared role or
          an unmatched target path raise an explicit exception instead of falling back to a
          substitute role or path.
        """
        ...

    @operation
    @override
    def resolve_contract_files(
        self,
        target_path: str,
        workspace_dir: str,
        role_name: Optional[str] = None,
    ) -> Sequence[str]:
        """Resolves companion specification contracts and interface definitions for target.

        POSTCONDITIONS:
        - MUST resolve the target role from the supplied role name or the target path.
        - WHEN the target role is undeclared, MUST raise KeyError without substituting a fallback role.
        - WHEN the target path matches no configured file pattern of the target role, MUST raise ValueError.
        - WHEN a cross-unit dependency is declared as a silent cross-role dependency, MUST filter that dependency out of the resolved contract files.
        - WHEN a cross-unit dependency is declared as a star role dependency, MUST expand the specification contracts of that dependency into the resolved contract files.
        - MUST discover low-level spec contracts, interface protocols, and definitions for the target unit.

        GROUNDING:
        - Looks up the active workspace_registry.RoleDefinition through
          workspace_registry.WorkspaceRegistry.resolve_role_definition, raising the registry
          lookup exception for an undeclared role, and matches target_path against
          workspace_registry.RoleDefinition.writable_file_patterns, raising an unmatched-path
          exception when no configured pattern accepts the path.
        - Filters cross-unit dependencies against
          workspace_registry.RoleDefinition.silent_cross_role_deps so that a silent cross-role
          dependency contributes no contract files to the resolved sequence, and expands the
          low-level specification contracts of each
          workspace_registry.RoleDefinition.star_role_deps entry into the resolved sequence,
          discovering the dynamically defined star-role contracts through
          workspace_registry.WorkspaceRegistry.list_roles for the active role.
        - Resolves both cases without any synthetic fallback role, path, or contract entry.
        """
        ...
