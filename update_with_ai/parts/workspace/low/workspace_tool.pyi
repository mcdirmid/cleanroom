# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-12T18:21:03Z
# LAST_CHANGED: 2026-10-11T16:00:00Z
# CHANGE: add verification check failure postcondition and no_verify parameter to run_submit
# CODE_HASH: ad6ec47351b0
# SPEC_QA_AUDIT: 2026-10-12T18:21:03Z
# --- END CLEANROOM METADATA ---

"""Low-level interface specification for workspace_tool."""

from typing import Any, Dict, List, Optional, Protocol, Sequence, Tuple
from framework import operation, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
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
    ) -> int:
        """Evaluates dirty work in local workspace and prints ready tasks."""
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
        role_name: str,
        dir_scope: str = "staging",
        repo_root: Optional[str] = None,
        custom_dest: Optional[str] = None,
    ) -> int:
        """Commissions an isolated role workspace."""
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
