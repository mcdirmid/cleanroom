# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T23:58:18Z
# LAST_CHANGED: 2026-10-07T00:11:26Z
# CHANGE: add template materialization to grounding
# CODE_HASH: 531dad3a7a19
# LOW_QA_AUDIT: 2026-10-07T23:58:18Z
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
    def compute_role_work_queue(
        self,
        role_name: str,
        dir_scope: str,
        repo_root: str,
    ) -> tuple[Sequence[workspace_work.WorkQueueItem], Sequence[workspace_work.WorkQueueItem]]:
        """Computes ready and blocked dirty units directly from build manifests and metadata.

        GROUNDING:
        - Scans part directories in scope, checks dependencies, sorts ready tasks
          topologically, and materializes starter templates via dag_storage.DagStorage.materialize_template
          for missing ready files.
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
