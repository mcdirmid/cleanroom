"""Low-level interface specification for check."""

from typing import Optional, Protocol
from support.lib.framework import operation, singleton_type
from support.lib.lifecycle import Singleton
from session import AgentSessionTier


@singleton_type
class WorkspaceChecker(Singleton[AgentSessionTier], Protocol):
    """Executes work discovery and file verification for role workspaces."""

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
        - MUST configure PYTHONPATH in the execution environment to include the target package root and constituent support libraries.
        - MUST record verification execution records and target file hashes in the workspace to gate subsequent submit, blame, and fail commands.
        - WHEN verification checks pass on a target carrying unacted feedback, MUST surface the unacted feedback items with an explicit reminder that static checks do not verify runtime behavior or feedback resolution.
        - MUST execute verification checks and return exit code.
        """
        ...

    @operation
    def is_checked_since_modification(
        self,
        ws_root: str,
        target_path: str,
    ) -> bool:
        """Returns True if the target has been verified via check_files since its last modification."""
        ...

    @operation
    def record_check_executed(
        self,
        ws_root: str,
        target_path: str,
        passed: bool,
    ) -> None:
        """Records file verification execution and content hash in the workspace."""
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:46Z
# LAST_CHANGED: 2026-10-14T18:25:00Z
# CHANGE: Define check low-level interface specification
# SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
# --- END CLEANROOM METADATA ---
