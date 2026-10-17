# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:46Z
# LAST_CHANGED: 2026-10-14T17:40:00Z
# CHANGE: Define pending_impl low-level specification
# CODE_HASH: 7d52c3541d65
# SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation specification for pending_impl."""

from typing import Optional, Sequence
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
from session import AgentSessionTier
import cleanroom_files_ext
import dag_storage
import src_metadata
import pending
import role_registry


@singleton_type("agent_session")
class WorkspacePendingManager(
    pending.WorkspacePendingManager,
    InTier[AgentSessionTier],
):
    """Realizes pending buffer tracking, target removal, and dirty checks.

    GROUNDING:
    - Manages JSON-serialized pending target state in cleanroom_files_ext.PENDING_WORK_FILE,
      reading, writing, and removing targets from local buffer files.
    - Evaluates whether pending targets remain dirty across local workspace and canonical
      repository using src_metadata.SourceMetadataCoordinator.extract_metadata and
      role_registry.WorkspaceRegistry.resolve_role_definition.
    - Materializes starter templates for missing target files via
      dag_storage.DagStorage.materialize_template.
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
        - Filters out target path or stem matching submitted target from
          cleanroom_files_ext.PENDING_WORK_FILE without wiping non-matching targets.
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
          configured feedback role targets from role_registry.WorkspaceRegistry.resolve_role_definition,
          evaluating producer targets across implicit role dependencies and star role dependencies,
          and materializing missing files via dag_storage.DagStorage.materialize_template.
        """
        ...
