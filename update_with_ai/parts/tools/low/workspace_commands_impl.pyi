# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:46Z
# LAST_CHANGED: 2026-10-14T17:50:00Z
# CHANGE: Define workspace_commands_impl low-level implementation specification
# CODE_HASH: a9484d347801
# SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation specification for workspace_commands_impl."""

from typing import Optional
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import cleanroom_files_ext
import workspace_commands
import workspace_check
import workspace_registry
import workspace_provision
import workspace_sync
import workspace_pending
import control_submit
import control_attribution
import tool_coverage


@singleton_type("agent_session")
class WorkspaceCommandHandler(
    workspace_commands.WorkspaceCommandHandler,
    InTier[AgentSessionTier],
):
    """Realizes substantive domain operations for Cleanroom role workspaces.

    GROUNDING:
    - Realizes workspace command execution by delegating work discovery and file
      verification to workspace_check.WorkspaceChecker, coordinating pending work buffer
      tracking via workspace_pending.WorkspacePendingManager, submission gating via
      control_submit.SubmissionCoordinator, blame attribution via
      control_attribution.AttributionCoordinator, coverage evaluation via
      tool_coverage.CoverageEvaluator, system synchronization via
      workspace_sync.WorkspaceSynchronizer, and lifecycle provisioning via
      workspace_provision.WorkspaceProvisioner and workspace_registry.WorkspaceRegistry.
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
        - Delegates work discovery directly to workspace_check.WorkspaceChecker.run_get_work.
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
        - Delegates file verification directly to workspace_check.WorkspaceChecker.run_check_files.
        """
        ...

    @operation
    @override
    def run_submit(
        self,
        target: str,
        summary: Optional[str] = None,
        repo_root: Optional[str] = None,
        no_verify: bool = False,
    ) -> int:
        """Verifies and submits target to canonical main repository.

        GROUNDING:
        - Validates target, executes role verification checks unless bypassed, delegates submission to
          control_submit.SubmissionCoordinator, appends submission message to cleanroom_files_ext.CLEANROOM_LOG_FILE
          in the directory containing parts, clears target via workspace_pending.WorkspacePendingManager.remove_pending_target,
          and updates local file.
        """
        ...

    @operation
    @override
    def run_blame(
        self,
        culprit_file: str,
        critique: str,
        repo_root: Optional[str] = None,
    ) -> int:
        """Attributes defect critique to culprit target in main repository.

        GROUNDING:
        - Validates single-paragraph critique, delegates attribution to
          control_attribution.AttributionCoordinator, appends blame message to
          cleanroom_files_ext.CLEANROOM_LOG_FILE in the directory containing parts,
          and clears target from pending work via workspace_pending.WorkspacePendingManager.
        """
        ...

    @operation
    @override
    def run_fail(
        self,
        file_path: str,
        reason: Optional[str] = None,
        repo_root: Optional[str] = None,
    ) -> int:
        """Marks target dirty and records failure feedback diagnostics.

        GROUNDING:
        - Delegates failure marking and diagnostics recording to
          control_attribution.AttributionCoordinator, and clears target from pending work
          via workspace_pending.WorkspacePendingManager.
        """
        ...

    @operation
    @override
    def run_coverage(
        self,
        target: Optional[str] = None,
        impl: Optional[str] = None,
        test: Optional[str] = None,
        threshold: float = 0.0,
        update_log: Optional[str] = None,
        max_spans: Optional[int] = None,
        json_output: bool = False,
        repo_root: Optional[str] = None,
    ) -> int:
        """Evaluates statement test coverage across target implementation and test.

        GROUNDING:
        - Evaluates test coverage via tool_coverage.CoverageEvaluator using local workspace files
          and formats diagnostic span reports.
        """
        ...

    @operation
    @override
    def run_commission(
        self,
        role_name: Optional[str] = None,
        dir_scope: Optional[str] = None,
        repo_root: Optional[str] = None,
        custom_dest: Optional[str] = None,
        all_roles: bool = False,
        reset: bool = False,
        model: Optional[str] = None,
    ) -> int:
        """Commissions an isolated role workspace or all workspaces in a directory scope.

        GROUNDING:
        - When all_roles is true, discovers all declared roles in dir_scope via workspace_registry.WorkspaceRegistry
          and commissions each role workspace via workspace_provision.WorkspaceProvisioner.commission.
        - Otherwise delegates workspace creation for role_name to workspace_provision.WorkspaceProvisioner.commission,
          propagating reset and model profile options.
        """
        ...

    @operation
    @override
    def run_refresh_sys(
        self,
        role_name: Optional[str] = None,
        dir_scope: Optional[str] = None,
        repo_root: Optional[str] = None,
    ) -> int:
        """Refreshes system files, bin tools, configs, and guides across role workspaces.

        GROUNDING:
        - Refreshes non-parts system files into active workspaces via
          workspace_sync.WorkspaceSynchronizer.refresh_system_files.
        """
        ...
