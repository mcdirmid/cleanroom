# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-14T17:50:00Z
# CHANGE: Delegate command workflows to workspace_commands
# CODE_HASH: 50e1815c1375
# SPEC_QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation specification for workspace_tool_impl."""

from typing import Optional, Sequence
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import workspace_commands
import workspace_tool


@singleton_type("agent_session")
class WorkspaceToolRunner(
    workspace_tool.WorkspaceToolRunner,
    InTier[AgentSessionTier],
):
    """Realizes command-line subagent tool execution for role workspaces.

    GROUNDING:
    - Realizes workspace tool CLI execution by coordinating argument parsing and
      delegating substantive command execution to workspace_commands.WorkspaceCommandHandler.
    """

    @operation
    @override
    def execute_command(self, argv: Sequence[str]) -> int:
        """Parses arguments and dispatches command execution, returning exit code.

        GROUNDING:
        - Constructs argparse subcommands for get_work, check_files, submit, blame, feedback, fail,
          coverage, commission, and refresh-sys, supporting repository root overrides for blame, fail,
          and coverage, and dispatching to runner operations within the agent session lifecycle tier.
        """
        ...

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
        - Delegates execution to workspace_commands.WorkspaceCommandHandler.run_get_work.
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
        - Delegates execution to workspace_commands.WorkspaceCommandHandler.run_check_files.
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
        - Delegates execution to workspace_commands.WorkspaceCommandHandler.run_submit.
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
        - Delegates execution to workspace_commands.WorkspaceCommandHandler.run_blame.
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
        - Delegates execution to workspace_commands.WorkspaceCommandHandler.run_fail.
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
        - Delegates execution to workspace_commands.WorkspaceCommandHandler.run_coverage.
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
        - Delegates execution to workspace_commands.WorkspaceCommandHandler.run_commission.
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
        - Delegates execution to workspace_commands.WorkspaceCommandHandler.run_refresh_sys.
        """
        ...
