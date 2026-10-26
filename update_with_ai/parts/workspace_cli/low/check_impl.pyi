"""Low-level implementation specification for check_impl."""

from typing import Optional
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import Singleton
from session import AgentSessionTier
import submit
import check
import pending
import role_registry
import sync
import work


@singleton_type("agent_session")
class WorkspaceChecker(check.WorkspaceChecker):
    """Realizes work discovery and file verification for role workspaces.

    GROUNDING:
    - Realizes work discovery by pulling changes via
      sync.WorkspaceSynchronizer.pull and sync.WorkspaceSynchronizer.refresh_system_files,
      checking pending targets via pending.WorkspacePendingManager.is_pending_target_dirty,
      scheduling work via work.WorkspaceWorkManager.compute_role_work_queue,
      and managing pending buffer via pending.WorkspacePendingManager.set_pending_work.
    - Realizes file verification by resolving targets via
      submit.SubmissionCoordinator.resolve_submit_target,
      regenerating missing templates via work.WorkspaceWorkManager.compute_role_work_queue
      and role_registry.WorkspaceRegistry.resolve_role_definition,
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
        - Evaluates dirty work using work.WorkspaceWorkManager.compute_role_work_queue,
          formats ready and blocked items with actionable next steps directing immediate
          round conclusion when zero ready targets remain and blocked targets are pending,
          resolving workspace-relative companion guide paths,
          and records pending targets using pending.WorkspacePendingManager.set_pending_work.
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
        - Resolves target via submit.SubmissionCoordinator.resolve_submit_target,
          extracts max_failures from active model configuration (defaulting to 5 for local engines and 100 for non-local models) and propagates failure limits to test execution runners,
          assembles verification environment bounded strictly to the active role workspace and its constituent package directories, isolating verification from the canonical repository root in PYTHONPATH and sys.path,
          enforces an execution timeout on verification commands to prevent blocked sub-processes from stalling the workspace developer loop and reports verification failure with code-defect diagnostic messaging when execution expires,
          executes verification checks from role_registry.RoleDefinition, and
          records verification execution records and target file hashes in the workspace.
        """
        ...

    @operation
    @override
    def is_checked_since_modification(
        self,
        ws_root: str,
        target_path: str,
    ) -> bool:
        """Returns True if the target has been verified via check_files since its last modification."""
        ...

    @operation
    @override
    def record_check_executed(
        self,
        ws_root: str,
        target_path: str,
        passed: bool,
    ) -> None:
        """Records file verification execution and content hash in the workspace."""
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-26T12:40:00Z
# LAST_CHANGED: 2026-10-26T12:40:00Z
# CHANGE: Clarify in check_files that verification timeouts indicate code defects rather than infrastructure failures
# SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
# --- END CLEANROOM METADATA ---
