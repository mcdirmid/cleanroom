# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:46Z
# LAST_CHANGED: 2026-10-14T08:35:00Z
# CHANGE: add feedback throttling postcondition to run_get_work
# CODE_HASH: af7f8e29272b
# SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
# --- END CLEANROOM METADATA ---

"""Low-level interface specification for cli_tool."""

from typing import Any, Dict, List, Optional, Protocol, Sequence, Tuple
from framework import operation, singleton_type
from support.lib.lifecycle import InTier
from session import AgentSessionTier
import cleanroom_files_ext


@singleton_type
class WorkspaceToolRunner(InTier[AgentSessionTier], Protocol):
    """Coordinates command-line subagent tool execution for role workspaces."""

    @operation
    def execute_command(self, argv: Sequence[str]) -> int:
        """Parses arguments and dispatches command execution, returning exit code."""
        ...

    @operation
    def run_get_work(
        self,
        dir_scope: Optional[str] = None,
        repo_root: Optional[str] = None,
        force: bool = False,
        batch_size: Optional[int] = None,
    ) -> int:
        """Evaluates dirty work in local workspace and prints ready tasks.

        POSTCONDITIONS:
        - WHEN batch_size is provided or resolved from configuration, MUST bound presented ready tasks to at most batch_size without extraneous remaining or blocked queue details.
        - WHEN unacted feedback reasons exceed max_feedback_chars resolved from configuration, MUST throttle presented feedback reasons to at most max_feedback_chars.
        - MUST evaluate dirty work in local workspace and print ready tasks.
        """
        ...

    @operation
    def run_check_files(
        self,
        target: Optional[str] = None,
        repo_root: Optional[str] = None,
    ) -> int:
        """Executes role-specific verification checks, linters, and type checking for targets.

        POSTCONDITIONS:
        - When a target file for a regenerable role is missing or deleted, MUST regenerate it from starter template.
        - WHEN verification checks pass on a target carrying unacted feedback, MUST surface the unacted feedback items with an explicit reminder that static checks do not verify runtime behavior or feedback resolution.
        - MUST execute verification checks and return exit code.
        """
        ...

    @operation
    def run_submit(
        self,
        target: str,
        summary: Optional[str] = None,
        repo_root: Optional[str] = None,
        no_verify: bool = False,
    ) -> int:
        """Verifies and submits target to canonical main repository.

        POSTCONDITIONS:
        - WHEN verification checks fail and no_verify is False, MUST reject submission and return non-zero exit code.
        - WHEN submission is accepted, MUST append submission message to cleanroom_files_ext.CLEANROOM_LOG_FILE in directory containing parts.
        - WHEN submission is accepted, MUST clear target from pending work.
        """
        ...

    @operation
    def run_blame(
        self,
        culprit_file: str,
        critique: str,
        repo_root: Optional[str] = None,
    ) -> int:
        """Attributes defect critique to culprit target in main repository.

        POSTCONDITIONS:
        - WHEN critique is accepted, MUST append blame message to cleanroom_files_ext.CLEANROOM_LOG_FILE in directory containing parts.
        - WHEN critique is accepted, MUST clear target from pending work.
        """
        ...

    @operation
    def run_fail(
        self,
        file_path: str,
        reason: Optional[str] = None,
        repo_root: Optional[str] = None,
    ) -> int:
        """Marks target dirty and records failure feedback diagnostics."""
        ...

    @operation
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
        """Evaluates statement test coverage across target implementation and test."""
        ...

    @operation
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
        """Commissions an isolated role workspace or all workspaces in a directory scope."""
        ...

    @operation
    def run_refresh_sys(
        self,
        role_name: Optional[str] = None,
        dir_scope: Optional[str] = None,
        repo_root: Optional[str] = None,
    ) -> int:
        """Refreshes system files, bin tools, configs, and guides across role workspaces."""
        ...
