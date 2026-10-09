# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-08T15:45:00Z
# LAST_CHANGED: 2026-10-08T15:45:00Z
# CHANGE: add template regeneration to run_check_files grounding
# CODE_HASH: 7a8b9c0d1e2f
# LOW_QA_AUDIT: 2026-10-08T12:00:00Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation specification for workspace_tool_impl."""

from typing import Optional, Sequence
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import workspace_tool
import workspace_registry
import workspace_provision
import workspace_sync
import workspace_work
import control_submit
import control_attribution
import tool_coverage


@singleton_type("agent_session")
class WorkspaceToolRunner(
    workspace_tool.WorkspaceToolRunner,
    InTier[AgentSessionTier],
):
    """Realizes command-line subagent tool execution for role workspaces.

    GROUNDING:
    - Realizes workspace tool CLI execution by coordinating argument parsing,
      inbound pulling via workspace_sync.WorkspaceSynchronizer, work queue evaluation
      and pending tracking via workspace_work.WorkspaceWorkManager, verification checks,
      submission gating via control_submit.SubmissionCoordinator, blame attribution
      via control_attribution.AttributionCoordinator, coverage evaluation via
      tool_coverage.CoverageEvaluator, and lifecycle provisioning via
      workspace_provision.WorkspaceProvisioner.
    """

    @operation
    @override
    def execute_command(self, argv: Sequence[str]) -> int:
        """Parses arguments and dispatches command execution, returning exit code.

        GROUNDING:
        - Constructs argparse subcommands for get_work, check_files, submit, blame, feedback, fail,
          coverage, commission, and refresh-sys, dispatching to runner operations.
        """
        ...

    @operation
    @override
    def run_get_work(
        self,
        dir_scope: Optional[str] = None,
        repo_root: Optional[str] = None,
        force: bool = False,
    ) -> int:
        """Evaluates dirty work in local workspace and prints ready tasks.

        GROUNDING:
        - Invokes workspace_sync.WorkspaceSynchronizer.pull and refresh_system_files,
          verifies pending target dirtiness, queries workspace_work.WorkspaceWorkManager.compute_role_work_queue,
          persists pending targets via workspace_work.WorkspaceWorkManager, and formats console instructions.
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
        - Resolves target paths and active role via workspace_registry.WorkspaceRegistry,
          regenerates missing target files from starter templates via workspace_work.WorkspaceWorkManager
          for regenerable roles, invokes verification rules, formats diagnostic reports, and returns exit status.
        """
        ...

    @operation
    @override
    def run_submit(
        self,
        target: str,
        summary: Optional[str] = None,
        repo_root: Optional[str] = None,
    ) -> int:
        """Verifies and submits target to canonical main repository.

        GROUNDING:
        - Validates target, delegates submission to control_submit.SubmissionCoordinator,
          appends submission message to .cleanroom.log in the directory containing parts,
          clears target via workspace_work.WorkspaceWorkManager, and updates local file.
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
          .cleanroom.log in the directory containing parts, and clears target from pending work.
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
          control_attribution.AttributionCoordinator, and clears target from pending work.
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
        role_name: str,
        dir_scope: str = "staging",
        repo_root: Optional[str] = None,
        custom_dest: Optional[str] = None,
    ) -> int:
        """Commissions an isolated role workspace.

        GROUNDING:
        - Delegates workspace creation to workspace_provision.WorkspaceProvisioner.commission.
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
