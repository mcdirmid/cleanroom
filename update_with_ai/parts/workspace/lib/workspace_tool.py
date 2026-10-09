# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
# LAST_CHANGED: 2026-10-06T23:30:00Z
# CHANGE: define workspace tool runner interface
# CODE_HASH: 8a4aafcea74a
# --- END CLEANROOM METADATA ---

"""Low-level interface specification for workspace_tool."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, Sequence, Tuple
from support.lib.lifecycle import get_singleton


class WorkspaceToolRunner(Protocol):
    """Coordinates command-line subagent tool execution for role workspaces."""

    def execute_command(self, argv: Sequence[str]) -> int:
        """Parses arguments and dispatches command execution, returning exit code."""
        ...

    def run_get_work(
        self,
        dir_scope: Optional[str] = None,
        repo_root: Optional[str] = None,
        force: bool = False,
    ) -> int:
        """Evaluates dirty work in local workspace and prints ready tasks."""
        ...

    def run_check_files(
        self,
        target: Optional[str] = None,
        repo_root: Optional[str] = None,
    ) -> int:
        """Executes role-specific verification checks, linters, and type checking for targets."""
        ...

    def run_submit(
        self,
        target: str,
        summary: Optional[str] = None,
        repo_root: Optional[str] = None,
    ) -> int:
        """Verifies and submits target to canonical main repository."""
        ...

    def run_blame(
        self,
        culprit_file: str,
        critique: str,
        repo_root: Optional[str] = None,
    ) -> int:
        """Attributes defect critique to culprit target in main repository."""
        ...

    def run_fail(
        self,
        file_path: str,
        reason: Optional[str] = None,
        repo_root: Optional[str] = None,
    ) -> int:
        """Marks target dirty and records failure feedback diagnostics."""
        ...

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

    def run_commission(
        self,
        role_name: str,
        dir_scope: str = "",
        repo_root: Optional[str] = None,
        custom_dest: Optional[str] = None,
    ) -> int:
        """Commissions an isolated role workspace."""
        ...

    def run_refresh_sys(
        self,
        role_name: Optional[str] = None,
        dir_scope: Optional[str] = None,
        repo_root: Optional[str] = None,
    ) -> int:
        """Refreshes system files, bin tools, configs, and guides across role workspaces."""
        ...


def get_workspace_tool_runner() -> WorkspaceToolRunner:
    """Returns singleton WorkspaceToolRunner instance."""
    return get_singleton(WorkspaceToolRunner)
