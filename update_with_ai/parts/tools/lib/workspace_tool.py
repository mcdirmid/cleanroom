# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-11T05:25:18Z
# CHANGE: Prune the uncontracted get_workspace_tool_runner module function and its lifecycle import so the interface holds only the declared runner protocol, restore the declared directory scope default, and carry the grounding specification's postconditions into the protocol docstrings
# CODE_HASH: a61a0558b455
# --- END CLEANROOM METADATA ---

"""Low-level interface specification for workspace_tool."""

from __future__ import annotations

from typing import Optional, Protocol, Sequence


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
        batch_size: Optional[int] = None,
    ) -> int:
        """Evaluates dirty work in local workspace and prints ready tasks."""
        ...

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
        - WHEN submission is accepted, MUST append submission message to .cleanroom.log in directory containing parts.
        - WHEN submission is accepted, MUST clear target from pending work.
        """
        ...

    def run_blame(
        self,
        culprit_file: str,
        critique: str,
        repo_root: Optional[str] = None,
    ) -> int:
        """Attributes defect critique to culprit target in main repository.

        POSTCONDITIONS:
        - WHEN critique is accepted, MUST append blame message to .cleanroom.log in directory containing parts.
        - WHEN critique is accepted, MUST clear target from pending work.
        """
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
        role_name: Optional[str] = None,
        dir_scope: Optional[str] = None,
        repo_root: Optional[str] = None,
        custom_dest: Optional[str] = None,
        all_roles: bool = False,
    ) -> int:
        """Commissions an isolated role workspace or all workspaces in a directory scope."""
        ...

    def run_refresh_sys(
        self,
        role_name: Optional[str] = None,
        dir_scope: Optional[str] = None,
        repo_root: Optional[str] = None,
    ) -> int:
        """Refreshes system files, bin tools, configs, and guides across role workspaces."""
        ...
