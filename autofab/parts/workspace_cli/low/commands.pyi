"""Low-level interface specification for commands."""

from typing import Optional, Protocol
from support.lib.framework import operation, singleton_type
from support.lib.lifecycle import Singleton
from session import AgentSessionTier
import autofab_files_ext


@singleton_type
class WorkspaceCommandHandler(Singleton[AgentSessionTier], Protocol):
    """Executes substantive domain operations for Autofab role workspaces."""

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
        - WHEN target is modified and has not been verified via check_files since modification and no_verify is False, MUST reject submission and return non-zero exit code.
        - WHEN staged blame entries exist for failing target, MUST commit staged blame to culprits, mark culprits dirty, clear staged blame buffer, and return zero exit code.
        - WHEN caller is an auditor role and no staged blame exists for target, MUST reject submission and return non-zero exit code.
        - WHEN verification checks fail without staged blame and no_verify is False, MUST reject submission and return non-zero exit code.
        - WHEN submission is accepted, MUST append submission message to autofab_files_ext.AUTOFAB_LOG_FILE both in the canonical repository and the local workspace root.
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
        - WHEN workspace target files are modified and have not been verified via check_files since modification, MUST reject blame attribution and return non-zero exit code.
        - WHEN caller role is configured and culprit role is neither in caller's feedback_role_deps nor star_feedback_role_deps, MUST reject blame attribution and return non-zero exit code.
        - WHEN structured blame experiment is active and critique fails structured blame validation (specification slug grounding in low specifications, violation taxonomy, facet noun phrase constraints, or symbol embargo), MUST reject blame attribution and return non-zero exit code.
        - MUST stage blame entry into workspace staged blame buffer rather than immediately committing attribution.
        """
        ...

    @operation
    def run_reject(
        self,
        file_path: str,
        reason: str,
        repo_root: Optional[str] = None,
    ) -> int:
        """Rejects active feedback on an unmodified target file and scrubs feedback from header.

        POSTCONDITIONS:
        - WHEN target file is modified since receiving feedback, MUST reject and return non-zero exit code.
        - WHEN target file has no active feedback in header, MUST reject and return non-zero exit code.
        - WHEN rejection is accepted, MUST scrub feedback header from target file.
        - WHEN rejection is accepted, MUST record rejection into autofab_files_ext.BLAME_BUFFER_FILE and append to autofab_files_ext.AUTOFAB_LOG_FILE.
        - WHEN rejection is accepted, MUST clear target from pending work.
        """
        ...

    @operation
    def run_fail(
        self,
        file_path: str,
        reason: Optional[str] = None,
        repo_root: Optional[str] = None,
    ) -> int:
        """Marks target dirty and records failure feedback diagnostics.

        POSTCONDITIONS:
        - WHEN target is modified and has not been verified via check_files since modification, MUST reject failure marking and return non-zero exit code.
        """
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

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:46Z
# LAST_CHANGED: 2026-11-07T10:20:00Z
# CHANGE: Define reject operation and stage-and-commit submit postconditions with auditor blame requirement
# SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
# --- END CLEANROOM METADATA ---
