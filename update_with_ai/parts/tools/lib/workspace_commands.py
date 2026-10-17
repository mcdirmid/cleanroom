# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-14T17:50:00Z
# CHANGE: Define workspace_commands interface protocol
# CODE_HASH: d93ce18ce31c
# COVERAGE_AUDIT: 2026-10-14T17:50:00Z
# QA_AUDIT: 2026-10-14T17:50:00Z
# --- END CLEANROOM METADATA ---

"""Low-level interface for workspace_commands."""

from __future__ import annotations

from typing import Optional, Protocol
from support.lib.lifecycle import InTier
from update_with_ai.parts.agent.lib.agent_session import AgentSessionTier


# Contract: WorkspaceCommandHandler protocol coordinates substantive domain operations for Cleanroom role workspaces.
class WorkspaceCommandHandler(InTier[AgentSessionTier], Protocol):
    """Executes substantive domain operations for Cleanroom role workspaces."""

    # Contract: Evaluates dirty work in local workspace and prints ready tasks, respecting batch_size and max_feedback_chars.
    def run_get_work(
        self,
        dir_scope: Optional[str] = None,
        repo_root: Optional[str] = None,
        force: bool = False,
        batch_size: Optional[int] = None,
    ) -> int:
        """Evaluates dirty work in local workspace and prints ready tasks."""
        ...

    # Contract: Executes role-specific verification checks, linters, and type checking for targets.
    def run_check_files(
        self,
        target: Optional[str] = None,
        repo_root: Optional[str] = None,
    ) -> int:
        """Executes role-specific verification checks, linters, and type checking for targets."""
        ...

    # Contract: Verifies and submits target to canonical main repository, recording in cleanroom log and clearing pending work.
    def run_submit(
        self,
        target: str,
        summary: Optional[str] = None,
        repo_root: Optional[str] = None,
        no_verify: bool = False,
    ) -> int:
        """Verifies and submits target to canonical main repository."""
        ...

    # Contract: Attributes defect critique to culprit target in main repository, recording in cleanroom log and clearing pending work.
    def run_blame(
        self,
        culprit_file: str,
        critique: str,
        repo_root: Optional[str] = None,
    ) -> int:
        """Attributes defect critique to culprit target in main repository."""
        ...

    # Contract: Marks target dirty and records failure feedback diagnostics.
    def run_fail(
        self,
        file_path: str,
        reason: Optional[str] = None,
        repo_root: Optional[str] = None,
    ) -> int:
        """Marks target dirty and records failure feedback diagnostics."""
        ...

    # Contract: Evaluates statement test coverage across target implementation and test.
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

    # Contract: Commissions an isolated role workspace or all workspaces in a directory scope.
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

    # Contract: Refreshes system files, bin tools, configs, and guides across role workspaces.
    def run_refresh_sys(
        self,
        role_name: Optional[str] = None,
        dir_scope: Optional[str] = None,
        repo_root: Optional[str] = None,
    ) -> int:
        """Refreshes system files, bin tools, configs, and guides across role workspaces."""
        ...

