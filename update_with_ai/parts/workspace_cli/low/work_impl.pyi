"""Low-level implementation specification for work_impl."""

from typing import Mapping, Optional, Sequence
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import Singleton
from session import AgentSessionTier
import work
import dirtiness
import pending
import work_scheduler
import src_metadata
import dag_storage
import role_registry
import cleanroom_files_ext


@singleton_type("agent_session")
class WorkspaceWorkManager(work.WorkspaceWorkManager):
    """Realizes work discovery across directory scopes and pending buffer tracking.

    GROUNDING:
    - Realizes work discovery by delegating directory-scoped scheduling to
      work_scheduler.WorkScheduler.schedule_work and ordering candidates through
      work_scheduler.WorkScheduler.compute_role_precedence, materializing starter
      templates via dag_storage.DagStorage.materialize_template, checking target metadata via
      src_metadata.SourceMetadataCoordinator.extract_metadata, delegating unit dirtiness evaluation
      and companion contract resolution to dirtiness.WorkspaceDirtinessEvaluator,
      evaluating auditor unit dirtiness across all feedback targets, evaluating producer unit dirtiness across implicit
      and star role dependencies, delegating pending work management to
      pending.WorkspacePendingManager, and managing pending work state in
      cleanroom_files_ext.PENDING_WORK_FILE.
    - Grounds companion contract resolution and cross-unit dependency filtering on
      role_registry.WorkspaceRegistry.resolve_role_definition and
      role_registry.WorkspaceRegistry.list_roles, reading
      role_registry.RoleDefinition.writable_file_patterns,
      role_registry.RoleDefinition.star_role_deps, and
      role_registry.RoleDefinition.silent_cross_role_deps to expand dynamically defined
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
        - Reads and parses JSON array from cleanroom_files_ext.PENDING_WORK_FILE.
        """
        ...

    @operation
    @override
    def clear_pending_work(self, workspace_dir: str) -> None:
        """Removes local pending work buffer file if present.

        GROUNDING:
        - Deletes cleanroom_files_ext.PENDING_WORK_FILE from workspace directory if it exists.
        """
        ...

    @operation
    @override
    def set_pending_work(self, workspace_dir: str, targets: Sequence[str]) -> None:
        """Records pending target paths into local buffer file.

        GROUNDING:
        - Writes targets sequence to cleanroom_files_ext.PENDING_WORK_FILE or removes file when empty.
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
        target_unit: Optional[str] = None,
    ) -> tuple[Sequence[work.WorkQueueItem], Sequence[work.WorkQueueItem]]:
        """Computes ready and blocked dirty units directly from build manifests and metadata.

        GROUNDING:
        - Scans part directories in scope, evaluates auditor units across all feedback role dependencies,
          evaluates producer units across intra-unit role dependencies and star role dependencies,
          bounds candidates to target_unit and its transitive dependencies when specified,
          checks upstream prerequisite roles across role dependencies, feedback role dependencies, star role dependencies, and silent role dependencies,
          relaxing intra-fuse upstream dependencies when evaluating a fused role cluster,
          sorts ready tasks topologically, and materializes starter templates via
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
        batch_size: Optional[int] = None,
    ) -> work.WorkQueueSummary:
        """Evaluates dirty units in scope and returns work queue summary.

        POSTCONDITIONS:
        - WHEN the supplied role is undeclared, MUST raise an explicit exception without substituting a fallback role.
        - WHEN a target path matches no configured file pattern of the supplied role, MUST raise an explicit exception without synthesizing a substitute path.

        GROUNDING:
        - Checks pending target dirtiness via src_metadata, schedules tasks via
          work_scheduler.WorkScheduler.schedule_work with dir_scope, bounds ready tasks to
          batch_size when provided, records ready targets, and formats the WorkQueueSummary.
        - Resolves the active role_registry.RoleDefinition through
          role_registry.WorkspaceRegistry.resolve_role_definition and lets an undeclared role or
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
        - Looks up the active role_registry.RoleDefinition through
          role_registry.WorkspaceRegistry.resolve_role_definition, raising the registry
          lookup exception for an undeclared role, and matches target_path against
          role_registry.RoleDefinition.writable_file_patterns, raising an unmatched-path
          exception when no configured pattern accepts the path.
        - Filters cross-unit dependencies against
          role_registry.RoleDefinition.silent_cross_role_deps so that a silent cross-role
          dependency contributes no contract files to the resolved sequence, and expands the
          low-level specification contracts of each
          role_registry.RoleDefinition.star_role_deps entry into the resolved sequence,
          discovering the dynamically defined star-role contracts through
          role_registry.WorkspaceRegistry.list_roles for the active role.
        - Resolves companion interface contracts without the _impl suffix for any implementation unit ending in _impl when expanding star role dependencies, without any synthetic fallback role.
        """
        ...

    @operation
    def get_part_units(
        self,
        repo_root: str,
        part_dir: str,
    ) -> Mapping[str, Sequence[str]]:
        """Discovers package unit names and dependencies from specifications or filesystem stems.

        GROUNDING:
        - Parses high/*.md specs for imports/implements/assembles metadata, falling back to filesystem stems.

        POSTCONDITIONS:
        - MUST discover unit names and dependencies from high-level specifications or filesystem stems in a part directory.
        """
        ...


def __orphan__() -> None:
    """Orphan contracts for package unit discovery routines.

    POSTCONDITIONS:
    - MUST discover unit names and dependencies from high-level specifications or filesystem stems in a part directory.
    """
    ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-26T20:38:00Z
# LAST_CHANGED: 2026-10-26T20:38:00Z
# CHANGE: Add intra-fuse dependency relaxation grounding to work_impl specification
# SPEC_QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---
