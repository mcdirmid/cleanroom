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
        - Evaluates dirty work using work.WorkspaceWorkManager.compute_role_work_queue against the canonical main workspace using canonical main_dir_scope (projecting discovered target paths to the role workspace leaf directory scope) when running in an isolated role workspace,
          relisting assigned pending targets when prior dirty work is already set,
          verifies when gemini-argon is configured on the antigravity harness that the active subagent conversation is executing on gemini-argon,
          for auditor roles aggressively executes verification checks on each discovered ready dirty target,
          automatically submitting passing targets via submit.SubmissionCoordinator.submit_target_file and omitting them from presented work,
          while retaining failing targets in the ready queue without outputting failure diagnostics during get_work,
          formats ready and blocked items with a prominent round conclusion directive directing immediate
          round conclusion without further tool calls when zero ready targets remain,
          resolving workspace-relative companion guide paths,
          surfaces dirty reasons and unacted feedback for presented and pending targets,
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
          enforces that verification cannot be executed when the role workspace has zero pending work assigned and zero ready items in the active work queue when no target is specified, returning an error directing the agent to call get_work first or conclude the round (while reporting no targets to check when neither target nor pending work is present),
          verifies that any specified target file belongs to the active pending work buffer, ready work queue, or is owned by the active role before executing checks, returning an error when an unassigned target not owned by the active role is requested,
          pulls inbound changes and refreshes system files from the canonical main workspace via sync.WorkspaceSynchronizer.pull and sync.WorkspaceSynchronizer.refresh_system_files before executing verification checks,
          verifies that package __init__.py and other read-only files outside the role's writeable file patterns have not been modified, reporting verification failure and reverting unauthorized modifications when detected,
          assembles verification environment bounded strictly to the active role workspace and its constituent package directories, isolating verification from the canonical repository root in PYTHONPATH and sys.path and configuring UV_CACHE_DIR under temporary directories (e.g. /tmp/uv_cache) for sandbox containment,
          enforces an execution timeout on verification commands to prevent blocked sub-processes from stalling the workspace developer loop and reports verification failure with code-defect diagnostic messaging when execution expires,
          executes verification checks from role_registry.RoleDefinition,
          sanitizes verification process output by stripping redundant embedded arbiter reminders before display,
          formats clean diagnostic outcomes reporting for non-auditor roles that all local verification checks passed and that other checks to verify feedback or changes resolution will be performed after bin/submit is called,
          formats triage summaries extracting author change headers, primary failure diagnostics, and candidate culprits, along with prominent specification grounding reminders upon verification failure when executing in auditor roles directing blame feedback strictly in terms of how the blamed file is not compliant with the common source of truth specification, permitting line numbers only within the blamed file while strictly forbidding exposing details of other files or authoring debug scripts, and instructing the agent when an uncovered line persists across rounds or after test updates to examine the library implementation closely to determine whether the line is structurally or logically unreachable,
          records verification execution records and target file hashes in the workspace, and upon zero verification errors for authoring roles with writable targets,
          records an in-workspace git milestone commit snapshot preserving the verified target state (omitting milestone commits for auditor roles with zero writable targets).
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
# LAST_CLEANED: 2026-10-30T11:00:00Z
# LAST_CHANGED: 2026-11-11T23:00:00Z
# CHANGE: Evaluate canonical main_dir_scope when discovering work from main in isolated workspaces
# SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
# --- END CLEANROOM METADATA ---
