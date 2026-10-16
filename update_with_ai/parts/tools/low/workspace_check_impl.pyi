# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:46Z
# LAST_CHANGED: 2026-10-14T18:25:00Z
# CHANGE: Define workspace_check_impl low-level implementation specification
# CODE_HASH: 30d2d82bbc05
# SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation specification for workspace_check_impl."""

from typing import Optional
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import control_submit
import workspace_check
import workspace_pending
import workspace_registry
import workspace_sync
import workspace_work


@singleton_type
class WorkspaceChecker(
    workspace_check.WorkspaceChecker,
    InTier[AgentSessionTier],
):
    """Realizes work discovery and file verification for role workspaces.

    GROUNDING:
    - Realizes work discovery by pulling changes via
      workspace_sync.WorkspaceSynchronizer.pull and workspace_sync.WorkspaceSynchronizer.refresh_system_files,
      checking pending targets via workspace_pending.WorkspacePendingManager.is_pending_target_dirty,
      scheduling work via workspace_work.WorkspaceWorkManager.compute_role_work_queue,
      and managing pending buffer via workspace_pending.WorkspacePendingManager.set_pending_work.
    - Realizes file verification by resolving targets via
      control_submit.SubmissionCoordinator.resolve_submit_target,
      regenerating missing templates via workspace_work.WorkspaceWorkManager.compute_role_work_queue
      and workspace_registry.WorkspaceRegistry.resolve_role_definition,
      and executing verification commands.
    """

    @operation
    @override
    def run_get_work(
        self,
        dir_scope: Optional[str] = None,
        repo_root: Optional[str] = None,
        force: bool = False,
        batch_size: Optional[int] = None,
    ) -> int:
        """Evaluates dirty work in local workspace and prints ready tasks.

        GROUNDING:
        - Evaluates dirty work using workspace_work.WorkspaceWorkManager.compute_role_work_queue
          and records pending targets using workspace_pending.WorkspacePendingManager.set_pending_work.
        """
        ...

    @operation
    @override
    def run_check_files(
        self,
        target: Optional[str] = None,
        repo_root: Optional[str] = None,
    ) -> int:
        """Executes role-specific verification checks, linters, and type checking for targets.

        GROUNDING:
        - Resolves target via control_submit.SubmissionCoordinator.resolve_submit_target and
          executes verification checks from workspace_registry.RoleDefinition.
        """
        ...
