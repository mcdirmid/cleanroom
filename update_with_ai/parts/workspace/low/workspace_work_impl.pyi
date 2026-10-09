# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
# LAST_CHANGED: 2026-10-09T04:30:00Z
# CHANGE: factor auditor unit dirtiness across all feedback targets and strict pending target removal
# CODE_HASH: e10735abf975
# LOW_QA_AUDIT: 2026-10-09T21:19:01Z
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
      control_work_scheduler.WorkScheduler, materializing starter templates via
      dag_storage.DagStorage.materialize_template, checking target metadata via src_metadata,
      evaluating auditor unit dirtiness across all feedback targets,
      and managing pending work state in .cleanroom_pending_work.json.
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
        - Checks target metadata via src_metadata across local workspace and main repository,
          evaluating auditor role targets across all configured feedback role targets.
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

        GROUNDING:
        - Checks pending target dirtiness via src_metadata, schedules tasks via
          control_work_scheduler.WorkScheduler with dir_scope, records ready targets,
          and formats the WorkQueueSummary.
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

        GROUNDING:
        - Discovers companion specification contracts, interface protocols, and definitions
          for target unit using role definitions from workspace_registry.WorkspaceRegistry.
        """
        ...
